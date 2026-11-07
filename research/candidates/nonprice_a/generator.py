"""Fixed Wikipedia attention-surge research indicator; no fitted parameters.

Dates are calendar anchors, not verified publication timestamps. Query-2 days
is a declared conservative lag, not evidence of historical availability.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd

CONFIG = {"recent_days": 30, "baseline_days": 365, "lag_days": 2,
          "neutral": 0.5, "max_count": 2**53 - 1, "column": "attention_surge_risk"}


def generate(observations: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Return every requested date; invalid/missing history is neutral and flagged."""
    source = observations[["Date", "wikipedia_pageviews"]].copy()
    source["Date"] = pd.to_datetime(source["Date"], errors="raise")
    dates = pd.DatetimeIndex(dates)
    for index in [pd.DatetimeIndex(source["Date"]), dates]:
        if index.hasnans or index.has_duplicates or index.tz is not None or not index.equals(index.normalize()):
            raise ValueError("unique timezone-naive calendar dates required")
    series = source.set_index("Date")["wikipedia_pageviews"].sort_index()
    rows = []
    for query in dates:
        end = query - pd.Timedelta(days=CONFIG["lag_days"])
        window = pd.date_range(end=end, periods=395, freq="D")
        # Select the past before numeric conversion: future poison is irrelevant.
        values = pd.to_numeric(series.reindex(window), errors="coerce").to_numpy(dtype=float)
        valid = np.isfinite(values) & (values >= 0) & (values <= CONFIG["max_count"]) & (values == np.floor(values))
        complete = bool(valid.all())
        risk, reason = 0.5, "missing_or_invalid_history"
        if complete:
            baseline, recent = values[:365].mean(), values[365:].mean()
            if baseline > 0:
                risk, reason = float(recent / (recent + baseline)), "available"
            else:
                reason = "zero_baseline"
        rows.append({"Date": query, "attention_surge_risk": risk,
                     "available": reason == "available", "status": reason,
                     "valid_days": int(valid.sum())})
    return pd.DataFrame(rows, columns=["Date", "attention_surge_risk", "available", "status", "valid_days"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = pd.read_csv(args.bundle / "wikipedia_pageviews_btc.csv")
    result = generate(source, pd.date_range("2014-12-31", "2022-12-31", freq="ME"))
    with args.output.open("x") as stream:
        result.to_csv(stream, index=False)


if __name__ == "__main__":
    main()
