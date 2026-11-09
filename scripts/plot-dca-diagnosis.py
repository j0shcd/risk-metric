"""Render a static diagnostic chart from hash-checked result tables; no UI."""
import argparse
import hashlib
import io
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = json.loads((args.input / "summary.json").read_text())
    raw = (args.input / "summary.csv").read_bytes()
    if hashlib.sha256(raw).hexdigest() != report["output_sha256"]["summary.csv"]:
        raise ValueError("summary identity mismatch")
    data = pd.read_csv(io.BytesIO(raw))
    labels = {
        "fixed_dca": "Fixed DCA", "incumbent": "Current composite",
        "price_only": "Price-only control", "raw_directed_mean": "Remove extra min/max transform",
        "single_top_reversal": "Top-reversal component alone", "single_bottom_reversal": "Bottom-reversal component alone",
        "single_cycle_extension": "Cycle-extension component alone", "single_cycle_regime": "Cycle-regime component alone",
        "without_top_reversal": "Drop top-reversal component", "without_bottom_reversal": "Drop bottom-reversal component",
        "without_cycle_extension": "Drop cycle-extension component", "without_cycle_regime": "Drop cycle-regime component",
        "causal_rank_24": "Causal percentile transform", "inverted_composite": "Reverse composite (direction check)",
        "six_month_deadline": "Current score + six-month deadline", "blind_six_month_delay": "Blind six-month delay",
        "fixed80_incumbent20": "80% Fixed DCA + 20% current",
    }
    fig, axis = plt.subplots(figsize=(11, 8), layout="constrained")
    y = np.arange(len(data))
    for i, row in data.iterrows():
        color = {"incumbent": "#0072B2", "single_top_reversal": "#D55E00", "six_month_deadline": "#009E73"}.get(row.arm, "#777777")
        axis.plot([100 * row.p10_delta, 100 * row.p90_delta], [i, i], color=color, lw=2, alpha=.65)
        axis.scatter(100 * row.median_delta, i, color=color, s=35, zorder=3)
    axis.axvline(0, color="#222222", lw=.9)
    axis.set_yticks(y, [labels[x] for x in data.arm])
    axis.invert_yaxis()
    axis.set_xlabel("BTC accumulated versus Fixed DCA (%)")
    axis.grid(axis="x", alpha=.2)
    axis.set_title("Reducing deferral helps; the positive ablation remains unvalidated", pad=14)
    fig.supxlabel("Dots: medians. Lines: 10th–90th percentiles of 96 overlapping four-year windows, not confidence intervals.\n"
                  "Same monthly budget, full terminal deployment, 0.20% costs, zero cash yield. All 17 frozen diagnostic arms shown.\n"
                  "Frozen repository evidence, December 2014–October 2026; diagnosis 9 November 2026.", fontsize=8)
    fig.savefig(args.output, dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
