"""Registered six-month decision-target experiment; no production integration.

Freeze before assessment. All source/input identities and numerical runtimes
are bound. Failed arms remain visible; a historical gain does not promote a model.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import platform
import sys
import time

import numpy as np
import pandas as pd

from . import decision_readout as readout


ROOT = Path(__file__).resolve().parents[1]
REGISTRATION = "docs/artifacts/target-readout-2026-11-10-registration.json"
REGISTRATION_SHA = "32d923c5329a475f201015e9487494b937212ae1f8b25cb3832cbc240b3359df"
CODE = ("research/decision_readout.py", "research/target_readout_study.py",
        "research/location_scale_readout.py", "research/distribution_readout.py",
        "tests/test_decision_readout.py", "tests/test_target_readout_study.py")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def runtime():
    return {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__}


def specification():
    raw = (ROOT / REGISTRATION).read_bytes()
    if sha(raw) != REGISTRATION_SHA:
        raise ValueError("registration changed")
    return json.loads(raw)


def identities():
    return {name: sha((ROOT / name).read_bytes()) for name in (*CODE, REGISTRATION)}


def freeze(path):
    spec = specification()
    for name, expected in spec["input_sha256"].items():
        if sha((ROOT / name).read_bytes()) != expected:
            raise ValueError("registered input changed: "+name)
    data = {"schema": "target-readout-implementation-v1", "code_sha256": identities(), "runtime": runtime()}
    with Path(path).open("x") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")
    return data


def verify(path):
    spec = specification()
    raw = Path(path).read_bytes()
    data = json.loads(raw)
    if data["code_sha256"] != identities() or data["runtime"] != runtime():
        raise ValueError("implementation/runtime changed after freeze")
    return spec, sha(raw)


def capture_frame(path, expected, **kwargs):
    raw = Path(path).read_bytes()
    if sha(raw) != expected:
        raise ValueError("input identity mismatch")
    return pd.read_csv(io.BytesIO(raw), **kwargs)


def context_frame(price, index):
    series = pd.Series(np.asarray(price, float), index=index)
    logs = np.log(series)
    return pd.DataFrame({"price": series, "context_trend": logs.diff(12),
                         "context_volatility": logs.diff().rolling(6, min_periods=6).std(ddof=1)})


def market_frame(spec):
    names = spec["input_sha256"]
    component_name = next(k for k in names if k.endswith("monthly_components.csv"))
    components = capture_frame(ROOT / component_name, names[component_name], index_col=0, parse_dates=True)
    daily = capture_frame(ROOT / "data/btc_daily.csv", names["data/btc_daily.csv"], parse_dates=["Date"])
    if daily.Date.duplicated().any():
        raise ValueError("duplicate source price dates")
    prices = daily.set_index("Date").Price.loc[:spec["last_complete_month"]].resample("ME").last()
    if prices.isna().any() or not np.isfinite(prices).all() or not prices.gt(0).all():
        raise ValueError("invalid complete monthly price history")
    frame = context_frame(prices, prices.index).loc[components.index].copy()
    if not np.allclose(frame.price, components.btc_price):
        raise ValueError("score and price snapshots disagree")
    for col in ("dca_risk", *readout.COMPONENTS):
        frame[col] = components[col]
    if not np.isfinite(frame.to_numpy()).all():
        raise ValueError("missing common feature support")
    return frame


def make_world(world_id, law, spec, *, engineering=False):
    cfg = spec["synthetic"]
    if law not in cfg["laws"]:
        raise ValueError("unregistered world law")
    seed = cfg["engineering_seed"] if engineering else cfg["root_seed"]
    streams = [np.random.default_rng(np.random.SeedSequence([seed, world_id, stream])) for stream in (1, 2, 3)]
    n, phi = cfg["monthly_rows"], cfg["state_ar"]
    state, nuisance = np.empty(n), np.empty(n)
    for values, generator in ((state, streams[0]), (nuisance, streams[2])):
        noise = generator.normal(size=n)
        values[0] = noise[0]
        for i in range(1, n):
            values[i] = phi*values[i-1]+math.sqrt(1-phi**2)*noise[i]
    drift_loading = cfg["drift_loading"] if law == "persistent_drift" else 0.
    volatility_loading = cfg["volatility_loading"] if law == "persistent_volatility" else 0.
    noise = streams[1].normal(size=n-1)
    returns = (cfg["monthly_drift"] + drift_loading*state[:-1]
               + cfg["base_monthly_volatility"]*np.exp(volatility_loading*state[:-1])*noise)
    prices = np.exp(np.r_[0., np.cumsum(returns)])
    dates = pd.date_range("2012-01-31", periods=n, freq="ME")
    frame = context_frame(prices, dates)
    frame["exact"], frame["nuisance"] = state, nuisance
    frame["constant"], frame["duplicate"] = .5, frame.context_trend
    return frame.iloc[cfg["first_query_index"]:].copy()


def forecasts(frame, method, feature, horizon):
    y = readout.deferral_targets(frame.price, horizon)
    results = []
    for origin in range(len(frame)):
        record = readout.forecast_at(frame, origin, horizon, method, feature)
        scored = (origin+horizon+1 < len(frame)
                  and frame.index[origin+horizon+1]+pd.Timedelta(days=1) < frame.index[-1])
        record["scored"] = bool(scored and record["trained"])
        if record["scored"]:
            record.update(readout.score_forecast(record, y[origin]))
        results.append(record)
    return results


def ledger(price, risk, trained, *, mode="forecast", cap=None):
    """Independent cumulative-funding implementation of the fixed buy mechanics."""
    price, risk, trained = np.asarray(price, float), np.asarray(risk, float), np.asarray(trained, bool)
    if (price.shape != risk.shape or price.shape != trained.shape or not np.isfinite(price).all()
            or np.any(price <= 0) or np.isinf(risk).any() or np.any((risk[np.isfinite(risk)] < 0) | (risk[np.isfinite(risk)] > 1))):
        raise ValueError("invalid common ledger support")
    spent, units, rows = 0., 0., []
    for i, px in enumerate(price):
        available = i+1-spent
        if mode == "fixed" or (mode == "forecast" and not trained[i]):
            target = 1.
        else:
            strength = max(0., 1.-4.*risk[i]) if np.isfinite(risk[i]) else 0.
            target = 1.+2.*strength if strength > 0 else 0.
        if cap is not None:
            target = max(target, max(0., i-cap+1-spent))
        natural = min(available, target)
        forced = available-natural if i == len(price)-1 else 0.
        buy = natural+forced
        spent += buy
        units += buy*.998/px
        rows.append({"buy": buy, "sweep": forced, "cash": i+1-spent, "units": units})
    result = pd.DataFrame(rows)
    assert np.isclose(spent, len(price)) and result.cash.ge(-1e-9).all()
    assert np.allclose(result.units, (result.buy*.998/price).cumsum())
    return result


def evaluate_market(frame, spec, output):
    issued, summaries = {}, []
    for arm in spec["market_forecasters"]:
        issued[arm["name"]] = forecasts(frame, arm["method"], arm["feature"], spec["horizon_months"])
    with gzip.open(output / "market_forecasts.json.gz", "wt") as stream:
        json.dump(issued, stream, allow_nan=False)
    # Forecast comparisons use exactly the same scored dates, not each arm's
    # preferred warm-up or its different count of mature labels.
    common = set.intersection(*[{r["date"] for r in records if r["scored"]} for records in issued.values()])
    for name, records in issued.items():
        selected = [r for r in records if r["date"] in common]
        summaries.append({"arm": name, "common_scored_n": len(selected),
                          **{metric: float(np.mean([r[metric] for r in selected])) for metric in ("crps", "brier", "coverage80", "width80")},
                          "fitted_origins": sum(r["trained"] for r in records),
                          "first_fitted_origin": next((r["date"] for r in records if r["trained"]), None)})
    pd.DataFrame(summaries).to_csv(output / "market_forecast_summary.csv", index=False)
    rows = []
    native_risk = frame.dca_risk.shift(1).to_numpy()
    main_mask = np.r_[False, [r["trained"] for r in issued["gaussian_components"][:-1]]]
    for start in range(len(frame)-48+1):
        window = frame.iloc[start:start+48]
        prices = window.price.to_numpy()
        fixed = ledger(prices, np.zeros(48), np.ones(48, bool), mode="fixed")
        for name in [*spec["market_controls"], *issued]:
            cap = None
            if name in issued:
                previous = [None, *issued[name][:-1]][start:start+48]
                risk = np.array([r["risk"] if r and r["trained"] else np.nan for r in previous])
                trained = np.array([bool(r and r["trained"]) for r in previous])
                result = ledger(prices, risk, trained)
            elif name == "fixed_dca":
                result = fixed
            else:
                mode = "forecast" if name == "warmup_matched_incumbent" else "native"
                cap = 6 if name == "incumbent_capped6" else None
                result = ledger(prices, native_risk[start:start+48], main_mask[start:start+48], mode=mode, cap=cap)
            rows.append({"arm": name, "start_date": str(window.index[0].date()), "end_date": str(window.index[-1].date()),
                         "btc_units": float(result.units.iloc[-1]), "fixed_btc_units": float(fixed.units.iloc[-1]),
                         "delta_vs_fixed": float(result.units.iloc[-1]/fixed.units.iloc[-1]-1),
                         "mean_wait_months": float(result.cash.sum()/48), "terminal_sweep_share": float(result.sweep.sum()/48)})
    windows = pd.DataFrame(rows)
    windows.to_csv(output / "market_windows.csv", index=False)
    summary, eras = [], []
    for name, group in windows.groupby("arm", sort=False):
        delta = group.delta_vs_fixed
        summary.append({"arm": name, "windows": len(group), "wins": int(delta.gt(1e-12).sum()),
                        "median_delta": float(delta.median()), "p10_delta": float(delta.quantile(.1)), "p90_delta": float(delta.quantile(.9))})
        years = pd.to_datetime(group.start_date).dt.year
        for lo, hi in ((2014, 2017), (2018, 2020), (2021, 2022)):
            d = group.loc[years.between(lo, hi), "delta_vs_fixed"]
            eras.append({"arm": name, "start_years": f"{lo}-{hi}", "windows": len(d),
                         "wins": int(d.gt(1e-12).sum()), "median_delta": float(d.median())})
    pd.DataFrame(summary).to_csv(output / "market_summary.csv", index=False)
    pd.DataFrame(eras).to_csv(output / "market_eras.csv", index=False)
    return {"common_forecast_origins": sorted(common), "summary": summary, "forecasts": summaries}


def evaluate_world(world_id, law, spec, output, *, engineering=False):
    frame = make_world(world_id, law, spec, engineering=engineering)
    all_records, means = [], []
    for horizon in spec["synthetic"]["horizons"]:
        cells = {}
        for method in spec["readouts"]:
            for arm in spec["synthetic"]["arms"]:
                cells[method, arm] = forecasts(frame, method, arm, horizon)
        common = set.intersection(*[{r["date"] for r in records if r["scored"]} for records in cells.values()])
        for (method, arm), records in cells.items():
            selected = [r for r in records if r["date"] in common]
            means.append({"world_id": world_id, "law": law, "horizon": horizon, "method": method, "arm": arm,
                          "scored_n": len(selected), **{m: float(np.mean([r[m] for r in selected]))
                                                           for m in ("crps", "brier", "coverage80", "width80")}})
            all_records.extend([{**r, "world_id": world_id, "law": law} for r in selected])
    with gzip.open(output / f"world-{law}-{world_id:02d}.json.gz", "wt") as stream:
        json.dump(all_records, stream, allow_nan=False)
    return means


def summarize_worlds(rows, spec):
    frame = pd.DataFrame(rows)
    rng = np.random.default_rng(spec["synthetic"]["bootstrap_seed"])
    count = len(spec["synthetic"]["world_ids"])
    indices = rng.integers(0, count, size=(spec["synthetic"]["bootstrap_world_resamples"], count))
    report = []
    for (law, horizon), group in frame.groupby(["law", "horizon"], sort=False):
        base = group[(group.method == "empirical_latest24") & (group.arm == "price_only")].sort_values("world_id")
        for (method, arm), cell in group.groupby(["method", "arm"], sort=False):
            cell = cell.sort_values("world_id")
            assert cell.world_id.to_list() == base.world_id.to_list() == spec["synthetic"]["world_ids"]
            own_reference = group[(group.method == method) & (group.arm == "price_only")].sort_values("world_id")
            delta = own_reference.crps.to_numpy()-cell.crps.to_numpy()
            boot = delta[indices].mean(axis=1)
            report.append({"law": law, "horizon": int(horizon), "method": method, "arm": arm, "worlds": len(cell),
                           "mean_crps": float(cell.crps.mean()), "mean_brier": float(cell.brier.mean()),
                           "coverage80": float(cell.coverage80.mean()), "mean_width80": float(cell.width80.mean()),
                           "gain_vs_own_price_only": float(delta.mean()),
                           "gain_ci95_pointwise": np.quantile(boot, [.025, .975]).tolist(),
                           "gain_vs_old_price_only": float(np.mean(base.crps.to_numpy()-cell.crps.to_numpy()))})
    return report


def run(freeze_path, output):
    spec, freeze_sha = verify(freeze_path)
    frame = market_frame(spec)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    network_attempts = []
    def offline(event, arguments):
        if event in ("socket.connect", "socket.getaddrinfo", "socket.sendto"):
            network_attempts.append(event)
            raise RuntimeError("network disabled in frozen assessment")
    sys.addaudithook(offline)
    worlds, failures = [], []
    for law in spec["synthetic"]["laws"]:
        for world_id in spec["synthetic"]["world_ids"]:
            if time.monotonic()-started > spec["budget"]["wall_clock_cap_seconds"]:
                failures.append({"law": law, "world_id": world_id, "reason": "wall_clock_budget"})
                continue
            try:
                worlds.extend(evaluate_world(world_id, law, spec, output))
                print(f"completed {law} world {world_id}", flush=True)
            except Exception as error:
                failures.append({"law": law, "world_id": world_id, "reason": type(error).__name__+": "+str(error)})
    pd.DataFrame(worlds).to_csv(output / "world_means.csv", index=False)
    with (output / "failures.json").open("x") as stream:
        json.dump(failures, stream, indent=2)
    if failures:
        raise RuntimeError("incomplete assessment; results retained, no replacement jobs")
    synthetic = summarize_worlds(worlds, spec)
    with (output / "synthetic_summary.json").open("x") as stream:
        json.dump(synthetic, stream, indent=2, allow_nan=False)
    frame.to_csv(output / "market_inputs.csv", index_label="date")
    market = evaluate_market(frame, spec, output)
    if network_attempts:
        raise RuntimeError("network attempts detected; no completed report")
    report = {"schema": "target-readout-result-v1", "freeze_sha256": freeze_sha,
              "runtime": runtime(), "completed_world_law_jobs": 96, "failures": failures,
              "network_attempts": network_attempts,
              "synthetic": synthetic, "market": market, "elapsed_seconds": time.monotonic()-started,
              "status": "exploratory_research_not_production_acceptance",
              "output_sha256": {p.name: sha(p.read_bytes()) for p in sorted(output.iterdir()) if p.is_file()}}
    with (output / "summary.json").open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print("study complete", output, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    freezing = sub.add_parser("freeze")
    freezing.add_argument("--output", required=True, type=Path)
    running = sub.add_parser("run")
    running.add_argument("--freeze", required=True, type=Path)
    running.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "freeze":
        freeze(args.output)
    else:
        run(args.freeze, args.output)


if __name__ == "__main__":
    main()
