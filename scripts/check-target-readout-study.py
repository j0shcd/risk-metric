#!/usr/bin/env python3
"""Check recorded forecasts and cash ledgers without importing their producer."""
import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import statistics


METRICS = ("crps", "brier", "coverage80", "width80")


def close(actual, expected):
    if not math.isclose(float(actual), float(expected), rel_tol=1e-9, abs_tol=1e-10):
        raise ValueError(f"numeric mismatch: {actual} != {expected}")


def table(raw):
    return list(csv.DictReader(io.StringIO(raw.decode())))


def scores(record):
    y = record["outcome"]
    if record["kind"] == "gaussian":
        mean, sigma = record["mean"], record["sigma"]
        if not sigma > 0:
            raise ValueError("nonpositive forecast scale")
        z = (y-mean)/sigma
        loss = sigma*(z*math.erf(z/math.sqrt(2))
                      + math.sqrt(2/math.pi)*math.exp(-z*z/2)-1/math.sqrt(math.pi))
        close(record["risk"], .5*math.erfc(-mean/(math.sqrt(2)*sigma)))
    else:
        atoms, weights = record["atoms"], record["weights"]
        close(sum(weights), 1)
        if min(weights) < 0:
            raise ValueError("negative atom weight")
        loss = sum(w*abs(x-y) for x, w in zip(atoms, weights))
        loss -= .5*sum(a*b*abs(x-z) for x, a in zip(atoms, weights)
                       for z, b in zip(atoms, weights))
        close(record["risk"], sum(w for x, w in zip(atoms, weights) if x > 0))
    result = (loss, (record["risk"]-(y > 0))**2,
              int(record["lo80"] <= y <= record["hi80"]), record["hi80"]-record["lo80"])
    for metric, value in zip(METRICS, result):
        close(record[metric], value)
    if not record["cal_last_label_available"] < record["date"]:
        raise ValueError("calibration uses unavailable outcome")
    if record["method"] != "empirical_latest24":
        if not record["fit_last_label_available"] < record["cal_first_origin"]:
            raise ValueError("fit/calibration chronology violated")
        if set(record["train_indices"]) & set(record["cal_indices"]):
            raise ValueError("fit/calibration overlap")
    return result


def balance(prices, risks, fallback, cap=None):
    # Cash recurrence is independent of the producer's cumulative-funding ledger.
    cash, units, cash_sum, sweep = 0., 0., 0., 0.
    for i, (price, risk, is_fallback) in enumerate(zip(prices, risks, fallback)):
        cash += 1
        request = 1. if is_fallback else (3-8*risk if risk is not None and risk < .25 else 0.)
        if cap:
            request = max(request, cash-cap)
        buy = min(cash, request)
        if i == 47:
            sweep = cash-buy
            buy = cash
        units += buy*.998/price
        cash -= buy
        if cash < -1e-9:
            raise ValueError("borrowing")
        cash_sum += cash
    close(cash, 0)
    return units, cash_sum/48, sweep/48


def check(root):
    report = json.loads((root/"summary.json").read_bytes())
    if report["failures"] or report["network_attempts"] or report["completed_world_law_jobs"] != 96:
        raise ValueError("incomplete or nonoffline assessment")
    captured = {}
    for name, expected in report["output_sha256"].items():
        if Path(name).name != name:
            raise ValueError("unsafe output name")
        raw = (root/name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("output hash mismatch: "+name)
        captured[name] = raw
    means = {(r["law"], int(r["world_id"]), int(r["horizon"]), r["method"], r["arm"]): r
             for r in table(captured["world_means.csv"])}
    if len(means) != 2304 or sum(name.startswith("world-") for name in captured) != 96:
        raise ValueError("missing registered worlds or cells")
    original_means = list(means.values())
    record_n = 0
    for name in sorted(n for n in captured if n.startswith("world-")):
        groups = {}
        for record in json.loads(gzip.decompress(captured[name])):
            key = (record["law"], record["world_id"], record["horizon"], record["method"], record["feature"])
            groups.setdefault(key, []).append((record["date"], scores(record)))
            record_n += 1
        supports = {}
        for key, rows in groups.items():
            dates = tuple(date for date, _ in rows)
            support_key = key[:3]
            if support_key in supports and dates != supports[support_key]:
                raise ValueError("unmatched synthetic score dates")
            supports[support_key] = dates
            expected = means.pop(key)
            close(expected["scored_n"], len(rows))
            for j, metric in enumerate(METRICS):
                close(expected[metric], statistics.mean(values[j] for _, values in rows))
    if means:
        raise ValueError("missing synthetic cells")
    for row in json.loads(captured["synthetic_summary.json"]):
        cell = [r for r in original_means if r["law"] == row["law"]
                and int(r["horizon"]) == row["horizon"] and r["method"] == row["method"] and r["arm"] == row["arm"]]
        for target, source in (("mean_crps", "crps"), ("mean_brier", "brier"),
                               ("coverage80", "coverage80"), ("mean_width80", "width80")):
            close(row[target], statistics.mean(float(r[source]) for r in cell))
        for target, method in (("gain_vs_own_price_only", row["method"]),
                               ("gain_vs_old_price_only", "empirical_latest24")):
            reference = [r for r in original_means if r["law"] == row["law"]
                         and int(r["horizon"]) == row["horizon"] and r["method"] == method and r["arm"] == "price_only"]
            close(row[target], statistics.mean(float(r["crps"]) for r in reference)-row["mean_crps"])
    market = table(captured["market_inputs.csv"])
    forecasts = json.loads(gzip.decompress(captured["market_forecasts.json.gz"]))
    for records in forecasts.values():
        for record in records:
            if record["scored"]:
                origin, horizon = record["origin"], record["horizon"]
                close(record["outcome"], math.log(float(market[origin+1]["price"])/float(market[origin+horizon+1]["price"])))
                scores(record)
    windows = table(captured["market_windows.csv"])
    if len(windows) != 1056:
        raise ValueError("missing registered ledger windows")
    for row in windows:
        start = next(i for i, r in enumerate(market) if r["date"] == row["start_date"])
        selected = market[start:start+48]
        prices = [float(r["price"]) for r in selected]
        if len(prices) != 48 or selected[-1]["date"] != row["end_date"]:
            raise ValueError("unequal window support")
        arm, risks, fallback = row["arm"], [], []
        for i in range(start, start+48):
            previous = forecasts[arm][i-1] if i and arm in forecasts else None
            if arm in forecasts:
                risks.append(previous["risk"] if previous and previous["trained"] else None)
                fallback.append(not previous or not previous["trained"])
            else:
                risks.append(float(market[i-1]["dca_risk"]) if i else None)
                fallback.append(arm == "fixed_dca" or (arm == "warmup_matched_incumbent"
                                and (not i or not forecasts["gaussian_components"][i-1]["trained"])))
        units, wait, sweep = balance(prices, risks, fallback, 6 if arm == "incumbent_capped6" else None)
        fixed = sum(.998/price for price in prices)
        for key, value in (("btc_units", units), ("fixed_btc_units", fixed),
                           ("delta_vs_fixed", units/fixed-1), ("mean_wait_months", wait),
                           ("terminal_sweep_share", sweep)):
            close(row[key], value)
    for row in table(captured["market_summary.csv"]):
        values = [float(r["delta_vs_fixed"]) for r in windows if r["arm"] == row["arm"]]
        close(row["median_delta"], statistics.median(values))
        close(row["wins"], sum(x > 1e-12 for x in values))
        close(row["windows"], len(values))
    for row in table(captured["market_forecast_summary.csv"]):
        records = [r for r in forecasts[row["arm"]] if r["date"] in report["market"]["common_forecast_origins"]]
        close(row["common_scored_n"], len(records))
        for metric in METRICS:
            close(row[metric], statistics.mean(r[metric] for r in records))
    return {"status": "passed", "independent_ledger_windows": len(windows),
            "synthetic_forecasts_rescored": record_n, "output_files_hash_checked": len(captured)}


def plot(root, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = table((root/"market_windows.csv").read_bytes())
    labels = {"incumbent": "Incumbent", "incumbent_capped6": "Incumbent, six-month cap",
              "warmup_matched_incumbent": "Incumbent, matched DCA warm-up",
              "empirical_latest24": "Six-month target, empirical latest 24",
              "empirical_split24": "Empirical, separate fit/calibration",
              "gaussian_split24": "Gaussian, matched split",
              "gaussian_expanding": "Gaussian, expanding composite",
              "gaussian_components": "Gaussian, four components",
              "gaussian_price_only": "Gaussian, price only",
              "gaussian_pooled": "Gaussian, pooled"}
    fig, ax = plt.subplots(figsize=(11, 6))
    for y, (arm, label) in enumerate(labels.items()):
        values = sorted(float(r["delta_vs_fixed"])*100 for r in rows if r["arm"] == arm)
        def q(p):
            index = p*(len(values)-1)
            lo = int(index)
            return values[lo]+(values[min(lo+1, len(values)-1)]-values[lo])*(index-lo)
        ax.plot([q(.1), q(.9)], [y, y], color="#777777", linewidth=2)
        ax.plot(statistics.median(values), y, "o", color="#0072B2")
    ax.axvline(0, color="black", linestyle="--", linewidth=1)
    ax.set_yticks(range(len(labels)), labels.values())
    ax.invert_yaxis()
    ax.set_xlabel("BTC units relative to Fixed DCA (%)")
    ax.set_title("No new forecast variant beats Fixed DCA at the historical median")
    ax.grid(axis="x", alpha=.2)
    fig.text(.02, .02, "Dots: medians; lines: 10th–90th percentiles, not confidence intervals.\n"
             "96 overlapping 48-contribution windows; full final deployment, zero yield, 0.20% costs. Frozen October 2026 snapshot.", fontsize=9)
    fig.tight_layout(rect=(0, .09, 1, 1))
    fig.savefig(output, dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--plot", type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.run), indent=2))
    if args.plot:
        plot(args.run, args.plot)
