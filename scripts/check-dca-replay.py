"""Independently reconcile and summarize an evaluate-dca-snapshot.py replay."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--plot", type=Path, help="Optional static figure; requires matplotlib")
    args = parser.parse_args()
    tables = args.run / "tables"
    manifest = json.loads((args.run / "manifest.json").read_text())
    for name, expected in manifest["table_sha256"].items():
        assert hashlib.sha256((tables / name).read_bytes()).hexdigest() == expected, name
    full = pd.read_csv(tables / "full_period_summary.csv")
    for strategy in full.strategy:
        ledger = pd.read_csv(tables / f"full_{strategy}.csv")
        expected_cash = (ledger.cash.shift(1).fillna(0) * 1.03 ** (1 / 12)
                         + ledger.contribution - ledger.buy_usd + ledger.sell_usd * .998)
        expected_units = (ledger.buy_usd * .998 / ledger.price - ledger.sell_usd / ledger.price).cumsum()
        assert np.allclose(ledger.cash, expected_cash, rtol=1e-10, atol=1e-10), strategy
        assert np.allclose(ledger.units, expected_units, rtol=1e-10, atol=1e-12), strategy
        assert np.allclose(ledger.equity, ledger.cash + ledger.units * ledger.price), strategy
        assert ledger.contribution.eq(1).all()
    windows = pd.read_csv(tables / "equal_horizon_windows.csv")
    assert windows.groupby(["start_date", "end_date", "matched_deployment"]).total_contributed.nunique().eq(1).all()
    matched = windows[windows.matched_deployment]
    assert np.allclose(matched.total_bought, 48) and matched.ending_cash.eq(0).all()
    assert np.allclose(matched.wealth_delta_pct_vs_fixed, matched.btc_delta_pct_vs_fixed)
    assert not manifest["network_attempts"]
    groups = []
    for (strategy, matched), group in windows.groupby(["strategy", "matched_deployment"]):
        values = group.wealth_delta_pct_vs_fixed
        groups.append({
            "strategy": strategy, "matched_deployment": bool(matched),
            "windows": len(group), "wins_vs_fixed": int(values.gt(0).sum()),
            "median_wealth_delta": float(values.median()),
            "p10_wealth_delta": float(values.quantile(.1)),
            "p90_wealth_delta": float(values.quantile(.9)),
            "median_purchase_spend_over_contributions": float((group.total_bought / group.total_contributed).median()),
            "median_btc_delta": float(group.btc_delta_pct_vs_fixed.median()),
        })
    strata = []
    risk = windows[windows.strategy.eq("risk_accumulation")].copy()
    risk["start_year"] = pd.to_datetime(risk.start_date).dt.year
    for matched in (False, True):
        for lo, hi in ((2014, 2017), (2018, 2020), (2021, 2022)):
            values = risk.loc[risk.matched_deployment.eq(matched) & risk.start_year.between(lo, hi), "wealth_delta_pct_vs_fixed"]
            strata.append({"start_years": [lo, hi], "matched_deployment": matched,
                           "windows": len(values), "wins": int(values.gt(0).sum()),
                           "median_wealth_delta": float(values.median())})
    summary = {"accounting_checks_passed": True, "equal_horizon_summary": groups,
               "exploratory_start_year_strata": strata,
               "finite_history_description_only": True,
               "not_a_production_acceptance_result": True}
    (args.run / "checked_summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    print(json.dumps(summary, indent=2))
    if args.plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True, layout="constrained")
        for matched, label, color, style in ((False, "Unchanged policy: cash allowed, 3% yield", "#0072B2", "-"),
                                              (True, "Equal deployment: final sweep, zero yield", "#D55E00", "--")):
            group = risk[risk.matched_deployment.eq(matched)]
            dates = pd.to_datetime(group.start_date)
            axes[0].plot(dates, 100 * group.wealth_delta_pct_vs_fixed, label=label, color=color, ls=style)
            axes[1].plot(dates, 100 * group.total_bought / group.total_contributed, color=color, ls=style)
        axes[0].axhline(0, color="#444444", lw=.8)
        axes[0].set_ylabel("Terminal wealth vs Fixed DCA (%)")
        axes[0].legend(loc="lower right", fontsize=8)
        axes[1].set_ylabel("Purchases / contributions (%)")
        axes[1].set_xlabel("Start date of 48-month contribution window")
        axes[1].set_ylim(0, 110)
        for axis in axes:
            axis.grid(alpha=.2)
        fig.suptitle("Equal final deployment still trails Fixed DCA in most historical windows")
        fig.supxlabel("96 overlapping windows, December 2014–October 2026; 0.20% trade costs.\n"
                       "Frozen repo data as of 9 November 2026. Exact history, no sampling confidence bands.", fontsize=8)
        fig.savefig(args.plot, dpi=160)
        plt.close(fig)


if __name__ == "__main__":
    main()
