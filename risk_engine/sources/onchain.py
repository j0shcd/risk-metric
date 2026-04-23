from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd

from ..config import RuntimeConfig
from .common import load_optional_csv, safe_get_json


GLASSNODE_BASE = "https://api.glassnode.com/v1/metrics"


def _parse_glassnode_series(payload: dict) -> Optional[pd.Series]:
    if not isinstance(payload, list):
        return None

    rows = []
    for item in payload:
        t = item.get("t")
        value = item.get("v")
        if t is None or value is None:
            continue
        rows.append((pd.to_datetime(int(t), unit="s").tz_localize(None).normalize(), float(value)))

    if not rows:
        return None

    frame = pd.DataFrame(rows, columns=["Date", "value"]).drop_duplicates(subset=["Date"]).sort_values("Date")
    return frame.set_index("Date")["value"]


def _fetch_glassnode_metric(cfg: RuntimeConfig, endpoint: str) -> Optional[pd.Series]:
    if not cfg.glassnode_api_key:
        return None

    payload = safe_get_json(
        url=f"{GLASSNODE_BASE}/{endpoint}",
        timeout_seconds=cfg.request_timeout_seconds,
        params={
            "a": "BTC",
            "i": "24h",
            "api_key": cfg.glassnode_api_key,
            "f": "json",
        },
    )

    if payload is None:
        return None

    return _parse_glassnode_series(payload)


def _fetch_coinmetrics_mvrv_fallback(cfg: RuntimeConfig) -> Optional[pd.Series]:
    # Community endpoint does not require a key for many metrics.
    payload = safe_get_json(
        url="https://community-api.coinmetrics.io/v4/timeseries/asset-metrics",
        timeout_seconds=cfg.request_timeout_seconds,
        params={
            "assets": "btc",
            "metrics": "CapMrktCurUSD,CapRealUSD",
            "frequency": "1d",
            "start_time": cfg.start_date,
        },
    )

    if payload is None:
        return None

    data = payload.get("data", [])
    if not data:
        return None

    frame = pd.DataFrame(data)
    if "time" not in frame.columns:
        return None

    for column in ["CapMrktCurUSD", "CapRealUSD"]:
        if column not in frame.columns:
            return None

    frame["Date"] = pd.to_datetime(frame["time"]).dt.tz_localize(None).dt.normalize()
    frame["CapMrktCurUSD"] = pd.to_numeric(frame["CapMrktCurUSD"], errors="coerce")
    frame["CapRealUSD"] = pd.to_numeric(frame["CapRealUSD"], errors="coerce")

    frame = frame.dropna(subset=["CapMrktCurUSD", "CapRealUSD"]).sort_values("Date")
    if frame.empty:
        return None

    spread = frame["CapMrktCurUSD"] - frame["CapRealUSD"]
    scale = frame["CapMrktCurUSD"].rolling(365, min_periods=90).std(ddof=0)
    mvrv_z = spread / scale.replace({0.0: np.nan})

    return pd.Series(mvrv_z.values, index=frame["Date"], name="mvrv_z_score")


def load_onchain_metrics(cfg: RuntimeConfig, index: pd.DatetimeIndex) -> pd.DataFrame:
    fallback_frame = None
    if cfg.onchain_fallback_csv and cfg.onchain_fallback_csv.exists():
        fallback_frame = pd.read_csv(cfg.onchain_fallback_csv, parse_dates=["Date"]).set_index("Date")
        fallback_frame.index = pd.to_datetime(fallback_frame.index).tz_localize(None)

    series_map: Dict[str, pd.Series] = {}

    mvrv = _fetch_glassnode_metric(cfg, endpoint="market/mvrv_z_score")
    if mvrv is None:
        mvrv = _fetch_coinmetrics_mvrv_fallback(cfg)
    if mvrv is None and fallback_frame is not None and "mvrv_z_score" in fallback_frame.columns:
        mvrv = fallback_frame["mvrv_z_score"].astype(float)
    series_map["mvrv_z_score"] = mvrv if mvrv is not None else pd.Series(dtype=float)

    puell = _fetch_glassnode_metric(cfg, endpoint="indicators/puell_multiple")
    if puell is None and fallback_frame is not None and "puell_multiple" in fallback_frame.columns:
        puell = fallback_frame["puell_multiple"].astype(float)
    series_map["puell_multiple"] = puell if puell is not None else pd.Series(dtype=float)

    supply_profit = _fetch_glassnode_metric(cfg, endpoint="supply/profit_relative")
    if supply_profit is None and fallback_frame is not None and "supply_in_profit" in fallback_frame.columns:
        supply_profit = fallback_frame["supply_in_profit"].astype(float)
    series_map["supply_in_profit"] = supply_profit if supply_profit is not None else pd.Series(dtype=float)

    out = pd.DataFrame(index=index)
    for name, series in series_map.items():
        if series.empty:
            out[name] = np.nan
            continue
        out[name] = series.reindex(index)

    out["supply_in_loss"] = 1.0 - out["supply_in_profit"]
    return out
