"""Independent cumulative-funding oracle for the frozen DCA diagnosis.

Does not import or call the diagnosis simulator. Cohorts are reconstructed by
overlap between cumulative purchase intervals and contribution-unit intervals.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    report = json.loads((args.input / "summary.json").read_text())
    frames = {}
    for name, expected in report["output_sha256"].items():
        raw = (args.input / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError(f"output hash mismatch: {name}")
        frames[name] = pd.read_csv(io.BytesIO(raw))
    monthly = frames["monthly_components.csv"].set_index("date")
    applied = frames["applied_scores.csv"].set_index("date")
    windows = frames["windows.csv"]
    cohort_table = frames["incumbent_cohorts.csv"]
    max_error, checked, cohort_count = 0.0, 0, 0
    for start, group in windows.groupby("start_date", sort=False):
        end = group.end_date.iloc[0]
        prices = monthly.loc[start:end, "btc_price"].to_numpy()
        assert len(prices) == 48 and len(group) == 17
        cache = {}
        # Reference must be reconstructed before its allocation overlay.
        ordered = ["incumbent"] + [a for a in group.arm if a != "incumbent"]
        for arm in ordered:
            scores = applied.loc[start:end, arm].to_numpy()
            spent = 0.0
            purchases, sweeps, remaining = [], [], []
            for month, score in enumerate(scores):
                available = month + 1 - spent
                if arm == "fixed_dca":
                    target = 1.0
                elif arm == "blind_six_month_delay":
                    target = float(month >= 6)
                elif arm == "fixed80_incumbent20":
                    target = .8 + .2 * (cache["incumbent"][0][month] - cache["incumbent"][1][month])
                else:
                    strength = max(0.0, 1.0 - 4.0 * score) if np.isfinite(score) else 0.0
                    target = 1.0 + 2.0 * strength if strength > 0 else 0.0
                if arm == "six_month_deadline":
                    due = max(0.0, month - 5 - spent)
                    target = max(target, due)
                natural = min(available, target)
                sweep = available - natural if month == 47 else 0.0
                bought = natural + sweep
                spent += bought
                purchases.append(bought)
                sweeps.append(sweep)
                remaining.append(month + 1 - spent)
            buys, forced = np.array(purchases), np.array(sweeps)
            cache[arm] = (buys, forced)
            units = float(np.dot(buys, .998 / prices))
            fixed_units = float(np.sum(.998 / prices))
            row = group[group.arm.eq(arm)].iloc[0]
            max_error = max(max_error, abs(units - row.btc_units))
            assert np.isclose(units, row.btc_units, rtol=1e-11, atol=1e-15), arm
            assert np.isclose(units / fixed_units - 1, row.delta_vs_fixed, atol=1e-12), arm
            assert np.isclose(sum(remaining) / 48, row.mean_wait_months, atol=1e-10), arm
            assert np.isclose(forced.sum() / 48, row.terminal_sweep_share, atol=1e-12), arm
            assert np.isclose(buys.sum(), 48) and min(remaining) >= -1e-10
            checked += 1
        buys = cache["incumbent"][0]
        upper = buys.cumsum()
        lower = upper - buys
        actual = cohort_table[cohort_table.start_date.eq(start)]
        assert len(actual) == 48
        for origin in range(48):
            allocation = np.maximum(0.0, np.minimum(origin + 1, upper) - np.maximum(origin, lower))
            units = float(np.dot(allocation, .998 / prices))
            wait = float(np.dot(allocation, np.arange(48) - origin))
            row = actual.iloc[origin]
            assert np.isclose(units, row.actual_units, rtol=1e-10, atol=1e-15)
            assert np.isclose(wait, row.wait_months, atol=1e-10)
            assert np.isclose((units - .998 / prices[origin]) / fixed_units, row.delta_contribution_to_window, atol=1e-11)
            cohort_count += 1
    print(json.dumps({"arm_window_balances_checked": checked, "cohorts_checked": cohort_count,
                      "maximum_btc_difference": max_error, "passed": True}, indent=2))


if __name__ == "__main__":
    main()
