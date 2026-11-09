"""Offline descriptive replay; never changes model acceptance or source caches.

Run with the repository's Python dependencies in an otherwise empty environment.
The output directory must not exist. Captures inputs before importing the model;
all pipeline writes occur in the captured scratch checkout under that directory.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import io
import json
import platform
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def capture(root: Path, output: Path) -> tuple[Path, dict]:
    paths = sorted((root / "risk_engine").rglob("*.py"))
    paths += sorted((root / "data").glob("*.csv"))
    paths += [root / "config" / name for name in (
        "model_acceptance_runtime.json", "model_acceptance.json",
        "ci_benchmark_baseline.json", "ci_benchmark_foundation.json",
    )]
    captured = {p.relative_to(root).as_posix(): p.read_bytes() for p in paths
                if "__pycache__" not in p.parts}
    snapshot = output / "snapshot"
    inventory = {}
    for relative, raw in captured.items():
        path = snapshot / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        item = {"sha256": sha256(raw), "bytes": len(raw)}
        if relative.startswith("data/"):
            rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
            dates = [r.get("Date") for r in rows if r.get("Date")]
            item.update(rows=len(rows), first_date=min(dates) if dates else None,
                        last_date=max(dates) if dates else None)
        inventory[relative] = item
    (snapshot / "config/runtime.json").write_bytes(captured["config/model_acceptance_runtime.json"])
    return snapshot, inventory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--as-of", required=True, help="Complete month-end, YYYY-MM-DD")
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    snapshot, inventory = capture(root, output)
    sys.path.insert(0, str(snapshot))
    network_attempts = []

    def offline_audit(event, arguments):
        if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
            network_attempts.append(event)
            raise RuntimeError("Network disabled for frozen-data evaluation")

    sys.addaudithook(offline_audit)
    import numpy as np
    import pandas as pd
    from dataclasses import replace
    from unittest.mock import patch
    from risk_engine.config import load_runtime_config
    from risk_engine.pipeline import run_pipeline
    from risk_engine.model_acceptance import current_identity
    from risk_engine.evaluation.config import build_evaluation_config
    from risk_engine.evaluation.checks import build_availability_calendar
    from risk_engine.evaluation.dca_evidence import (
        _accumulation_ledger, _accumulation_summary, _month_end_series,
        _price_only_risk, evaluate_dca_evidence,
    )

    cutoff = pd.Timestamp(args.as_of)
    if cutoff != cutoff + pd.offsets.MonthEnd(0):
        raise ValueError("as-of must be a complete month-end")
    if cutoff >= pd.Timestamp.now().normalize().replace(day=1):
        raise ValueError("as-of must precede the current month")
    identity = current_identity(snapshot)
    # Ambient provider keys and CSV path overrides must never escape the capture.
    with patch.dict("os.environ", {}, clear=True):
        cfg = replace(load_runtime_config(snapshot), end_date=args.as_of, refresh_api_sources=False)
    # Prevent cached rows beyond the cutoff entering any source-side transforms.
    # Inventory above binds the unmodified source bytes; record transformed bytes.
    transformations = {}
    for path in sorted((snapshot / "data").glob("*.csv")):
        frame = pd.read_csv(path)
        if "Date" not in frame:
            continue
        dates = pd.to_datetime(frame["Date"], errors="raise")
        if dates.duplicated().any():
            raise ValueError(f"duplicate dates in {path.name}")
        keep = dates <= cutoff
        frame.loc[keep].to_csv(path, index=False)
        transformations[path.name] = {
            "excluded_after_cutoff": int((~keep).sum()),
            "retained_rows": int(keep.sum()), "sha256": sha256(path.read_bytes()),
        }
    effective_identity = current_identity(snapshot)
    print("running current pipeline", head, args.as_of, flush=True)
    result = run_pipeline(cfg)
    series = result.series.loc[:cutoff]
    assert not series.index.has_duplicates and series.index.is_monotonic_increasing
    price_daily = series["btc_price"]
    assert (price_daily > 0).all() and np.isfinite(price_daily).all()
    assert series.index.max() == cutoff, "daily price coverage does not reach cutoff"
    policy_fields = {name: getattr(cfg, name) for name in asdict(cfg) if name.startswith("cycle_dynamic_dca_")}
    ev = build_evaluation_config(output_dir=output, profile="standard", run_id=f"fresh-dca-through-{args.as_of}", **policy_fields)
    tables = output / "tables"
    tables.mkdir()
    series.to_csv(tables / "daily_scores.csv", index_label="date")
    result.source_health.to_csv(tables / "source_health.csv", index=False)
    result.metric_health.to_csv(tables / "metric_health.csv", index=False)
    build_availability_calendar(result, ev).to_csv(tables / "availability_calendar.csv", index=False)
    print("running unchanged compact suite", flush=True)
    evidence = evaluate_dca_evidence(series, pd.DataFrame(), ev)
    for name in ("summary", "accumulation_windows", "policy_attribution_windows",
                 "derisking_windows", "signal_value", "causality_audit"):
        getattr(evidence, name).to_csv(tables / f"dca_{name}.csv", index=False)

    price = _month_end_series(series["btc_price"])
    score = _month_end_series(series["dca_risk"]).reindex(price.index)
    frame = pd.DataFrame({"price": price, "score": score,
                          "applied": score.shift(1),
                          "price_only_applied": _price_only_risk(price).shift(1)}).dropna(subset=["price", "score"])
    # Monthly calendar continuity, score bounds and strictly prior-month decisions.
    assert frame.index.equals(pd.date_range(frame.index[0], cutoff, freq="ME"))
    assert frame["score"].between(0, 1).all()
    frame.to_csv(tables / "monthly_inputs.csv", index_label="date")
    full_rows = []
    for strategy in ("fixed_dca", "risk_accumulation", "fixed_buys_risk_sells", "risk_buys_and_sells"):
        ledger = _accumulation_ledger(frame.price, frame.applied, strategy=strategy, config=ev)
        assert (ledger.cash >= -1e-9).all() and (ledger.units >= -1e-12).all()
        assert np.allclose(ledger.equity, ledger.cash + ledger.units * ledger.price)
        ledger.to_csv(tables / f"full_{strategy}.csv", index_label="date")
        full_rows.append({"strategy": strategy, **_accumulation_summary(ledger)})
    pd.DataFrame(full_rows).to_csv(tables / "full_period_summary.csv", index=False)

    # Supplementary 48-month starts: unchanged cash-allowed policy plus a matched
    # total-spend diagnostic. Zero interest and terminal sweep ensure exactly the
    # same principal is deployed. This is a different, explicitly labelled policy.
    import risk_engine.evaluation.dca_evidence as dca_module
    rows = []
    annual_yield = dca_module.ANNUAL_CASH_YIELD
    for start in range(len(frame) - 48 + 1):
        window = frame.iloc[start:start + 48]
        for matched in (False, True):
            dca_module.ANNUAL_CASH_YIELD = 0.0 if matched else annual_yield
            ledgers = {}
            for strategy in ("fixed_dca", "risk_accumulation", "price_only_accumulation"):
                applied = window.price_only_applied if strategy == "price_only_accumulation" else window.applied
                ledger = _accumulation_ledger(window.price, applied, strategy=strategy, config=ev)
                if matched:
                    # Final purchase includes the final scheduled contribution;
                    # same transaction cost, final date and final close for both.
                    cash = float(ledger.cash.iloc[-1])
                    ledger.loc[ledger.index[-1], "buy_usd"] += cash
                    ledger.loc[ledger.index[-1], "units"] += cash * (1.0 - ev.cycle_dynamic_dca_fee_rate - ev.cycle_dynamic_dca_slippage_rate) / float(window.price.iloc[-1])
                    ledger.loc[ledger.index[-1], "cash"] = 0.0
                    ledger.loc[ledger.index[-1], "equity"] = float(ledger.units.iloc[-1]) * float(window.price.iloc[-1])
                # Independent accounting reconstruction from actual executed buys.
                expected_units = (ledger.buy_usd * (1.0 - ev.cycle_dynamic_dca_fee_rate - ev.cycle_dynamic_dca_slippage_rate) / ledger.price).cumsum()
                assert np.allclose(ledger.units, expected_units)
                assert (ledger.sell_usd == 0).all()
                budget = float(ledger.contribution.sum())
                assert np.isclose(budget, 48 * ev.cycle_dynamic_dca_base_contribution)
                if matched:
                    assert np.isclose(ledger.buy_usd.sum(), budget) and ledger.cash.iloc[-1] == 0
                ledgers[strategy] = ledger
            fixed = ledgers["fixed_dca"]
            for strategy, ledger in ledgers.items():
                rows.append({
                    "start_date": str(window.index[0].date()), "end_date": str(window.index[-1].date()),
                    "strategy": strategy, "matched_deployment": matched,
                    "annual_cash_yield": 0.0 if matched else annual_yield,
                    "terminal_wealth": float(ledger.equity.iloc[-1]),
                    "btc_units": float(ledger.units.iloc[-1]),
                    "total_contributed": float(ledger.contribution.sum()),
                    "total_bought": float(ledger.buy_usd.sum()),
                    "ending_cash": float(ledger.cash.iloc[-1]),
                    "wealth_delta_pct_vs_fixed": float(ledger.equity.iloc[-1] / fixed.equity.iloc[-1] - 1),
                    "btc_delta_pct_vs_fixed": float(ledger.units.iloc[-1] / fixed.units.iloc[-1] - 1),
                })
    dca_module.ANNUAL_CASH_YIELD = annual_yield
    pd.DataFrame(rows).to_csv(tables / "equal_horizon_windows.csv", index=False)
    assert not network_attempts, network_attempts
    manifest = {
        "source_head": head, "runner_sha256": sha256(Path(__file__).read_bytes()),
        "as_of": args.as_of, "identity_raw": identity, "identity_truncated": effective_identity,
        "input_inventory": inventory, "cutoff_transformations": transformations,
        "resolved_runtime": asdict(cfg), "evaluation_config": asdict(ev),
        "cash_yield_annual": annual_yield,
        "python": platform.python_version(),
        "dependencies": {x: importlib.metadata.version(x) for x in (
            "numpy", "pandas", "requests", "certifi", "charset-normalizer", "idna",
            "python-dateutil", "pytz", "six", "tzdata", "urllib3")},
        "network_attempts": network_attempts, "source_modes": result.source_modes,
        "monthly_rows": len(frame), "first_month": str(frame.index[0].date()),
        "missing_score_days": int(series.dca_risk.isna().sum()),
        "table_sha256": {p.name: sha256(p.read_bytes()) for p in sorted(tables.glob("*.csv"))},
        "limitations": ["Exposed historical data; not a protected holdout or prospective test.",
                        "Overlapping windows are dependent; finite-history descriptions, no sampling confidence intervals.",
                        "Cached macro values have no verified release-vintage availability.",
                        "Current checked-in model under credential-free acceptance runtime fixture; not proof of deployed model identity.",
                        "Terminal-sweep zero-interest diagnostic changes the trading policy and is not an acceptance result."],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, default=str, indent=2, allow_nan=False) + "\n")
    print("complete", output, flush=True)


if __name__ == "__main__":
    main()
