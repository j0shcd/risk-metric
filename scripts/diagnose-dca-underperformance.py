"""Bounded, exploratory ledger diagnosis using authenticated prior replay bytes.

No downloads, model fitting, threshold search, production writes or UI launches.
The protocol fixes every arm before measurement. An absent output directory is
required. Diagnostic improvements are not prospective claims or promotions.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


COMPONENTS = {
    "top_reversal": "dca_top_reversal_component",
    "bottom_reversal": "dca_bottom_reversal_component",
    "cycle_extension": "dca_cycle_extension_component",
    "cycle_regime": "dca_cycle_regime_component",
}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def captured_csv(path: Path, expected: str, **kwargs) -> pd.DataFrame:
    raw = path.read_bytes()
    if digest(raw) != expected:
        raise ValueError(f"input identity mismatch: {path.name}")
    return pd.read_csv(io.BytesIO(raw), **kwargs)


def simulate(price, applied_score, *, kind="timing", deadline=None, schedule=None):
    """Allocate executed principal FIFO; each contribution is exactly one unit.

    Scores are already lagged. Fees/slippage consume 0.2% of each gross purchase.
    Every cohort is fully spent by the known final date. Waiting attribution is
    bookkeeping, not a claim about which fungible dollar an investor earmarked.
    """
    price = np.asarray(price, dtype=float)
    score = np.asarray(applied_score, dtype=float)
    if len(price) != len(score) or not len(price) or not np.isfinite(price).all() or (price <= 0).any():
        raise ValueError("invalid price/score calendar")
    if np.isinf(score).any() or ((score[np.isfinite(score)] < 0) | (score[np.isfinite(score)] > 1)).any():
        raise ValueError("score outside [0,1]")
    remaining = np.ones(len(price))
    cohort_units = np.zeros(len(price))
    cohort_wait = np.zeros(len(price))
    cash = units = 0.0
    rows = []
    for i, px in enumerate(price):
        cash += 1.0
        strength = max(0.0, (0.25 - score[i]) / 0.25) if np.isfinite(score[i]) else 0.0
        if schedule is not None:
            desired = float(schedule[i])
        elif kind == "fixed":
            desired = 1.0
        elif kind == "blind_delay":
            desired = 1.0 if i >= 6 else 0.0
        else:
            desired = 1.0 + 2.0 * strength if strength > 0 else 0.0
            if i >= 48:
                desired = max(desired, 1.0)
        if deadline is not None:
            due = float(remaining[:max(0, i - deadline + 1)].sum())
            desired = max(desired, due)
        natural_buy = min(max(desired, 0.0), cash)
        sweep = cash - natural_buy if i == len(price) - 1 else 0.0
        buy = natural_buy + sweep
        cash -= buy
        units += buy * .998 / px
        left = buy
        for origin in range(i + 1):
            take = min(remaining[origin], left)
            remaining[origin] -= take
            cohort_units[origin] += take * .998 / px
            cohort_wait[origin] += take * (i - origin)
            left -= take
            if left <= 1e-12:
                break
        assert abs(left) < 1e-9
        assert cash >= -1e-9 and np.isclose(cash, remaining[:i + 1].sum())
        if deadline is not None and i >= deadline:
            assert np.allclose(remaining[:i - deadline + 1], 0)
        rows.append({"price": px, "score_used": score[i], "buy": buy,
                     "terminal_sweep": sweep, "cash": cash, "units": units})
    ledger = pd.DataFrame(rows)
    assert np.isclose(ledger.buy.sum(), len(price)) and abs(cash) < 1e-9
    assert np.allclose(remaining, 0)
    assert np.isclose(cohort_units.sum(), units)
    assert np.allclose(ledger.units, (ledger.buy * .998 / price).cumsum())
    cohorts = pd.DataFrame({"origin": np.arange(len(price)), "fixed_units": .998 / price,
                            "actual_units": cohort_units, "weighted_wait_months": cohort_wait})
    cohorts["units_delta"] = cohorts.actual_units - cohorts.fixed_units
    return ledger, cohorts


def score_arms(monthly: pd.DataFrame) -> dict[str, pd.Series]:
    columns = list(COMPONENTS.values())
    directed = pd.DataFrame({"top": monthly.top_reversal_risk,
                             "bottom": 1.0 - monthly.bottom_reversal_risk,
                             "extension": monthly.cycle_extension_score,
                             "regime": monthly.cycle_frenzy_score})
    arms = {"fixed_dca": pd.Series(np.nan, index=monthly.index),
            "incumbent": monthly.dca_risk.shift(1),
            "price_only": monthly.price_only_applied,
            "raw_directed_mean": directed.mean(axis=1).shift(1)}
    for label, column in COMPONENTS.items():
        arms[f"single_{label}"] = monthly[column].shift(1)
        arms[f"without_{label}"] = monthly[[x for x in columns if x != column]].mean(axis=1).shift(1)
    rank = monthly.dca_risk.expanding(min_periods=24).rank(method="max", pct=True)
    arms["causal_rank_24"] = rank.fillna(monthly.dca_risk).shift(1)
    arms["inverted_composite"] = (1.0 - monthly.dca_risk).shift(1)
    for name in ("six_month_deadline", "blind_six_month_delay", "fixed80_incumbent20"):
        arms[name] = monthly.dca_risk.shift(1)
    return arms


def overlay_schedule(incumbent: pd.DataFrame) -> np.ndarray:
    # Preserve the forced portion as a forced sweep in the combined ledger.
    return .8 + .2 * (incumbent.buy - incumbent.terminal_sweep).to_numpy()


def calibration_audit(all_months: pd.DataFrame, root: Path) -> tuple[dict, pd.DataFrame]:
    # main authenticates every model source before this import.
    sys.path.insert(0, str(root))
    from risk_engine.calibration import _long_cycle_labels
    top, bottom = _long_cycle_labels(all_months.btc_price, horizons_months=[36, 48], lookback_months=24)
    table = pd.DataFrame({"top_label": top, "bottom_label": bottom})
    audit = {}
    for name, labels in (("top", top), ("bottom", bottom)):
        eligible = []
        for i, date in enumerate(labels.index):
            known = labels.iloc[:max(0, i - 48)].dropna()
            usable = len(known) >= 24 and int(known.eq(1).sum()) >= 3 and int(known.eq(0).sum()) >= 3
            if usable:
                eligible.append(str(date.date()))
        audit[name] = {"mature_labels": int(labels.notna().sum()), "positives": int(labels.eq(1).sum()),
                       "negatives": int(labels.eq(0).sum()), "eligible_selector_months_before_feature_missingness": len(eligible),
                       "first_eligible_month": eligible[0] if eligible else None}
    return audit, table


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--daily-scores", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    root = args.root.resolve()
    evidence = root / "docs/artifacts/dca-evaluation-2026-11-09"
    protocol_path = root / "docs/artifacts/dca-diagnosis-2026-11-09/protocol.json"
    protocol_raw = protocol_path.read_bytes()
    protocol = json.loads(protocol_raw)
    original = json.loads((evidence / "summary.json").read_text())
    for relative, metadata in original["manifest"]["input_inventory"].items():
        if relative.startswith("risk_engine/") or relative.startswith("config/"):
            if digest((root / relative).read_bytes()) != metadata["sha256"]:
                raise ValueError(f"source identity changed: {relative}")
    daily = captured_csv(args.daily_scores, protocol["daily_score_sha256"], index_col=0, parse_dates=True)
    published = captured_csv(evidence / "monthly_inputs.csv", protocol["published_monthly_sha256"], index_col=0, parse_dates=True)
    reference = captured_csv(evidence / "equal_horizon_windows.csv", protocol["published_equal_horizon_sha256"])
    assert daily.index.is_monotonic_increasing and not daily.index.has_duplicates
    all_months = daily.resample("ME").last()
    monthly = all_months.loc[published.index].copy()
    assert monthly.dca_risk.notna().all()
    assert np.allclose(monthly.btc_price, published.price) and np.allclose(monthly.dca_risk, published.score)
    monthly["price_only_applied"] = published.price_only_applied
    assert monthly.index.equals(pd.date_range(monthly.index[0], monthly.index[-1], freq="ME"))
    assert np.allclose(monthly[list(COMPONENTS.values())].mean(axis=1), monthly.dca_risk)
    arms = score_arms(monthly)
    assert set(arms) == set(protocol["arms"]) and len(arms) == 17
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    monthly[["btc_price", "dca_risk", *COMPONENTS.values(), "top_reversal_risk", "bottom_reversal_risk",
             "cycle_extension_score", "cycle_frenzy_score", "price_only_applied"]].to_csv(out / "monthly_components.csv", index_label="date")
    applied = pd.DataFrame(arms)
    applied.to_csv(out / "applied_scores.csv", index_label="date")
    rows, cohort_rows = [], []
    for start in range(len(monthly) - 48 + 1):
        window = monthly.iloc[start:start + 48]
        price = window.btc_price.to_numpy()
        incumbent, _ = simulate(price, arms["incumbent"].iloc[start:start + 48])
        fixed_units = float((.998 / price).sum())
        for name in protocol["arms"]:
            kind = "fixed" if name == "fixed_dca" else ("blind_delay" if name == "blind_six_month_delay" else "timing")
            schedule = overlay_schedule(incumbent) if name == "fixed80_incumbent20" else None
            ledger, cohorts = simulate(price, arms[name].iloc[start:start + 48], kind=kind,
                                       deadline=6 if name == "six_month_deadline" else None, schedule=schedule)
            units = float(ledger.units.iloc[-1])
            assert np.isclose(cohorts.units_delta.sum(), units - fixed_units)
            if name == "fixed80_incumbent20":
                assert np.isclose(units, .8 * fixed_units + .2 * incumbent.units.iloc[-1])
                assert np.allclose(ledger.buy, .8 + .2 * incumbent.buy)
                assert np.allclose(ledger.cash, .2 * incumbent.cash)
                assert np.allclose(ledger.terminal_sweep, .2 * incumbent.terminal_sweep)
            if name in {"fixed_dca", "incumbent", "price_only"}:
                strategy = {"fixed_dca": "fixed_dca", "incumbent": "risk_accumulation", "price_only": "price_only_accumulation"}[name]
                ref = reference[(reference.start_date == str(window.index[0].date())) & reference.strategy.eq(strategy) & reference.matched_deployment]
                assert len(ref) == 1 and np.isclose(units, ref.btc_units.iloc[0], rtol=1e-12), name
            rows.append({"arm": name, "start_date": str(window.index[0].date()), "end_date": str(window.index[-1].date()),
                         "btc_units": units, "fixed_btc_units": fixed_units, "delta_vs_fixed": units / fixed_units - 1,
                         "mean_wait_months": float(cohorts.weighted_wait_months.sum() / 48),
                         "terminal_sweep_share": float(ledger.terminal_sweep.sum() / 48),
                         "scheduled_buy_months": int((ledger.buy - ledger.terminal_sweep).gt(1e-10).sum())})
            if name == "incumbent":
                for origin, cohort in cohorts.iterrows():
                    cohort_rows.append({"start_date": str(window.index[0].date()), "arrival_date": str(window.index[origin].date()),
                                        "fixed_units": float(cohort.fixed_units), "actual_units": float(cohort.actual_units),
                                        "delta_contribution_to_window": float(cohort.units_delta / fixed_units),
                                        "wait_months": float(cohort.weighted_wait_months)})
    windows = pd.DataFrame(rows)
    windows.to_csv(out / "windows.csv", index=False)
    pd.DataFrame(cohort_rows).to_csv(out / "incumbent_cohorts.csv", index=False)
    summaries, eras = [], []
    for name, group in windows.groupby("arm", sort=False):
        delta = group.delta_vs_fixed
        summaries.append({"arm": name, "windows": len(group), "wins": int(delta.gt(1e-12).sum()),
                          "median_delta": float(delta.median()), "p10_delta": float(delta.quantile(.1)), "p90_delta": float(delta.quantile(.9)),
                          "median_wait_months": float(group.mean_wait_months.median()),
                          "median_terminal_sweep_share": float(group.terminal_sweep_share.median())})
        years = pd.to_datetime(group.start_date).dt.year
        for lo, hi in ((2014, 2017), (2018, 2020), (2021, 2022)):
            subset = group.loc[years.between(lo, hi), "delta_vs_fixed"]
            eras.append({"arm": name, "start_years": f"{lo}-{hi}", "windows": len(subset),
                         "wins": int(subset.gt(1e-12).sum()), "median_delta": float(subset.median())})
    pd.DataFrame(summaries).to_csv(out / "summary.csv", index=False)
    pd.DataFrame(eras).to_csv(out / "eras.csv", index=False)
    audit, label_table = calibration_audit(all_months, root)
    label_table.to_csv(out / "calibration_labels.csv", index_label="date")
    report = {"protocol_sha256": digest(protocol_raw), "script_sha256": digest(Path(__file__).read_bytes()),
              "daily_scores_sha256": protocol["daily_score_sha256"], "calibration_labels": audit,
              "component_correlation": monthly[list(COMPONENTS.values())].corr().to_dict(),
              "score_region_counts": {str(year): {"months": len(g), "low": int(g.dca_risk.le(.25).sum()), "high": int(g.dca_risk.ge(.75).sum())}
                                      for year, g in monthly.groupby(monthly.index.year)},
              "summary": summaries, "era_summary": eras,
              "checks": {"published_reference_rows_reconciled": 288, "all_arms_equal_budget": True,
                         "cohort_accounting_reconciles": True, "overlay_linear_identity": True},
              "interpretation": "Finite exposed-history diagnostics, not generalization or production acceptance. No arm chosen or fitted.",
              "output_sha256": {f.name: digest(f.read_bytes()) for f in sorted(out.glob("*.csv"))}}
    (out / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(pd.DataFrame(summaries).to_string(index=False))
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
