"""Strict daily-close endpoint construction for a retrospective BTC scorecard."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd


COMPONENTS = ("dca_risk", "dca_top_reversal_component", "dca_bottom_reversal_component",
              "dca_cycle_extension_component", "dca_cycle_regime_component")
TARGETS = ("terminal_log_return", "entry_adverse_log_loss", "peak_drawdown_log_loss")


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_snapshot(path: Path) -> dict:
    payload = path.read_bytes()
    frame = pd.read_csv(io.BytesIO(payload), index_col=0, parse_dates=True)
    if (frame.empty or not isinstance(frame.index, pd.DatetimeIndex) or frame.index.has_duplicates
            or not frame.index.is_monotonic_increasing or frame.index.tz is not None
            or not frame.index.equals(frame.index.normalize())
            or not {"btc_price", *COMPONENTS}.issubset(frame.columns)):
        raise ValueError("source requires unique ordered timezone-naive daily dates and all score columns")
    dates = pd.date_range(frame.index.min(), frame.index.max(), freq="D")
    frame = frame.reindex(dates)
    def finite_or_none(value):
        return float(value) if np.isfinite(float(value)) else None
    months = pd.date_range(dates.min(), dates.max(), freq="ME")
    # This fixed start belongs to the benchmark, independent of custom candidates.
    common = frame.loc[months, list(COMPONENTS)].notna().all(axis=1)
    if not common.any():
        raise ValueError("source has no complete baseline month")
    months = months[months >= common[common].index[0]]
    return {"schema": "retrospective-btc-snapshot-v1", "source_sha256": hashlib.sha256(payload).hexdigest(),
            "availability": "reconstructed historical scores; source vintages and UTC close convention unverified",
            "daily": [{"date": date.date().isoformat(), "price": finite_or_none(frame.loc[date, "btc_price"])} for date in dates],
            "monthly": [{"date": date.date().isoformat(), **{c: finite_or_none(frame.loc[date, c]) for c in COMPONENTS}}
                        for date in months]}


def build_dataset(snapshot: dict, horizons: list[int]) -> dict:
    if (not horizons or len(set(horizons)) != len(horizons)
            or any(type(h) is not int or h < 1 for h in horizons)):
        raise ValueError("horizons must be distinct positive diagnostic month counts")
    daily = snapshot["daily"]
    dates = pd.DatetimeIndex([row["date"] for row in daily])
    if dates.empty or not dates.equals(pd.date_range(dates.min(), dates.max(), freq="D")):
        raise ValueError("snapshot must explicitly retain every daily date, including missing prices")
    price = np.array([np.nan if row["price"] is None else row["price"] for row in daily], float)
    valid = np.isfinite(price) & (price > 0)
    log_price = np.full(len(price), np.nan)
    log_price[valid] = np.log(price[valid])
    rows = []
    previous = None
    for item in snapshot["monthly"]:
        decision = pd.Timestamp(item["date"])
        if decision != decision + pd.offsets.MonthEnd(0) or (previous is not None and decision <= previous):
            raise ValueError("snapshot decisions must be ordered unique complete month ends")
        previous = decision
        position = dates.get_indexer([decision])[0]
        if position < 0:
            raise ValueError("decision outside daily snapshot")
        lookback = dates.get_indexer([decision - pd.DateOffset(years=1)])[0]
        context = None
        if lookback >= 0 and valid[lookback:position + 1].all():
            trend = log_price[position] - log_price[lookback]
            volatility = float(np.std(np.diff(log_price[position - 90:position + 1]), ddof=1))
            drawdown = float(log_price[position] - np.max(log_price[lookback:position + 1]))
            context = [float(trend), volatility]
        else:
            drawdown = None
        entry = decision + pd.Timedelta(days=1)
        outcomes = {}
        for horizon in horizons:
            end = entry + pd.DateOffset(months=horizon)
            entry_i, end_i = dates.get_indexer([entry, end])
            status = "pending" if end > dates[-1] else "missing_price_path"
            values = None
            if entry_i >= 0 and end_i >= entry_i and valid[entry_i:end_i + 1].all():
                path = log_price[entry_i:end_i + 1]
                values = [float(path[-1] - path[0]), float(path[0] - path.min()),
                          float(np.max(np.maximum.accumulate(path) - path))]
                status = "complete"
            outcomes[str(horizon)] = {"status": status, "entry": entry.date().isoformat(),
                                     "end": end.date().isoformat(),
                                     "available": (end + pd.Timedelta(days=1)).date().isoformat(),
                                     "values": values}
        rows.append({"date": item["date"], "context": context, "outcomes": outcomes,
                     "indicators": {c: item[c] for c in COMPONENTS},
                     "references": {"price_trend_12m": context[0] if context else None,
                                    "price_volatility_90d": context[1] if context else None,
                                    "price_drawdown_12m": drawdown}})
    return {"schema": "daily-close-research-endpoints-v1", "horizons": horizons, "targets": list(TARGETS),
            "snapshot_id": digest(snapshot), "rows": rows}


def split_at(rows: list[dict], horizon: int, index: int, minimum: int = 24) -> tuple[list[int], list[int]]:
    """Separate fixed-size fit/calibration; every label is strictly mature."""
    key, cutoff = str(horizon), rows[index]["date"]
    mature = [i for i in range(index) if rows[i]["context"] is not None
              and rows[i]["outcomes"][key]["status"] == "complete"
              and rows[i]["outcomes"][key]["available"] < cutoff]
    calibration = mature[-minimum:]
    if len(calibration) < minimum:
        return [], []
    fit = [i for i in mature if rows[i]["outcomes"][key]["available"] < rows[calibration[0]]["date"]][-minimum:]
    return (fit, calibration) if len(fit) == minimum else ([], [])
