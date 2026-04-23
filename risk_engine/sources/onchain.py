from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

from ..config import RuntimeConfig
from .common import safe_get_json


GLASSNODE_BASE = "https://api.glassnode.com/v1/metrics"
CORE_METRICS = ["mvrv_z_score", "puell_multiple", "supply_in_profit"]


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


def _onchain_store_path(cfg: RuntimeConfig) -> Path:
    return cfg.onchain_fallback_csv or (cfg.cache_dir / "onchain_metrics.csv")


def _load_onchain_store(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    frame = pd.read_csv(path, parse_dates=["Date"])
    if "Date" not in frame.columns:
        return pd.DataFrame()
    frame["Date"] = pd.to_datetime(frame["Date"], utc=False).dt.tz_localize(None)
    frame = frame.set_index("Date")
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()

    for col in frame.columns:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")

    return frame


def _merge_metric(existing: Optional[pd.Series], updates: Optional[pd.Series], name: str) -> pd.Series:
    base = existing.astype(float) if existing is not None and not existing.empty else pd.Series(dtype=float, name=name)
    if updates is None or updates.empty:
        return base

    incoming = updates.astype(float)
    if base.empty:
        merged = incoming.sort_index()
    else:
        merged = pd.concat([base, incoming])
    merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    merged.name = name
    return merged


def _save_onchain_store(path: Path, metrics: Dict[str, pd.Series]) -> None:
    if not metrics:
        return

    frame = pd.DataFrame(metrics)
    if frame.empty:
        return

    frame = frame.sort_index()
    frame.index.name = "Date"
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.reset_index().to_csv(path, index=False)


def load_onchain_metrics(cfg: RuntimeConfig, index: pd.DatetimeIndex) -> pd.DataFrame:
    store_path = _onchain_store_path(cfg)
    fallback_frame = _load_onchain_store(store_path)
    series_map: Dict[str, pd.Series] = {}

    mvrv = _fetch_glassnode_metric(cfg, endpoint="market/mvrv_z_score")
    if mvrv is None:
        mvrv = _fetch_coinmetrics_mvrv_fallback(cfg)
    local_mvrv = fallback_frame["mvrv_z_score"] if "mvrv_z_score" in fallback_frame.columns else None
    series_map["mvrv_z_score"] = _merge_metric(local_mvrv, mvrv, "mvrv_z_score")

    puell = _fetch_glassnode_metric(cfg, endpoint="indicators/puell_multiple")
    local_puell = fallback_frame["puell_multiple"] if "puell_multiple" in fallback_frame.columns else None
    series_map["puell_multiple"] = _merge_metric(local_puell, puell, "puell_multiple")

    supply_profit = _fetch_glassnode_metric(cfg, endpoint="supply/profit_relative")
    local_supply = fallback_frame["supply_in_profit"] if "supply_in_profit" in fallback_frame.columns else None
    series_map["supply_in_profit"] = _merge_metric(local_supply, supply_profit, "supply_in_profit")

    # Keep unknown local columns if user stored additional on-chain metrics.
    for col in fallback_frame.columns:
        if col not in series_map:
            series_map[col] = fallback_frame[col].astype(float)

    _save_onchain_store(store_path, series_map)

    out = pd.DataFrame(index=index)
    for name in CORE_METRICS:
        series = series_map.get(name, pd.Series(dtype=float))
        if series.empty:
            out[name] = np.nan
            continue
        out[name] = series.reindex(index)

    out["supply_in_loss"] = 1.0 - out["supply_in_profit"]
    return out
