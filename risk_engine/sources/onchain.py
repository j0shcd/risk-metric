from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd
import requests

from ..config import RuntimeConfig

CORE_METRICS = ["mvrv_z_score", "puell_multiple", "supply_in_profit"]


def _fetch_coinmetrics_asset_metrics(
    cfg: RuntimeConfig,
    metrics: list[str],
) -> Optional[pd.DataFrame]:
    if not cfg.refresh_api_sources:
        return None

    if not metrics:
        return None

    try:
        response = requests.get(
            "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics",
            params={
                "assets": "btc",
                "metrics": ",".join(metrics),
                "frequency": "1d",
                "start_time": cfg.start_date,
                "page_size": 10000,
            },
            timeout=cfg.request_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return None

    data = payload.get("data", [])
    if not data:
        return None

    frame = pd.DataFrame(data)
    if "time" not in frame.columns:
        return None

    frame["Date"] = pd.to_datetime(frame["time"]).dt.tz_localize(None).dt.normalize()
    for metric in metrics:
        if metric in frame.columns:
            frame[metric] = pd.to_numeric(frame[metric], errors="coerce")
    frame = frame.dropna(subset=["Date"]).sort_values("Date")
    keep = ["Date"] + [m for m in metrics if m in frame.columns]
    frame = frame[keep]
    if frame.empty:
        return None

    return frame


def _mvrv_z_from_ratio(ratio: pd.Series) -> pd.Series:
    mean = ratio.expanding(min_periods=365).mean()
    std = ratio.expanding(min_periods=365).std(ddof=0).replace({0.0: np.nan})
    return (ratio - mean) / std


def _puell_from_issuance_usd(issuance_usd: pd.Series) -> pd.Series:
    denom = issuance_usd.rolling(365, min_periods=90).mean().replace({0.0: np.nan})
    return issuance_usd / denom


def _supply_in_profit_proxy_from_mvrv_ratio(mvrv_ratio: pd.Series) -> pd.Series:
    centered = (mvrv_ratio - 1.0).clip(lower=-2.0, upper=4.0)
    proxy = 1.0 / (1.0 + np.exp(-2.2 * centered))
    return proxy.clip(lower=0.0, upper=1.0)


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
    source_modes: Dict[str, str] = {}

    coinmetrics = _fetch_coinmetrics_asset_metrics(cfg, metrics=["CapMVRVCur", "IssTotUSD"])

    mvrv = None
    if coinmetrics is not None and "CapMVRVCur" in coinmetrics.columns:
        ratio = coinmetrics.set_index("Date")["CapMVRVCur"].dropna().astype(float)
        if not ratio.empty:
            mvrv = pd.Series(_mvrv_z_from_ratio(ratio), name="mvrv_z_score")
    mvrv_mode = "coinmetrics_community" if mvrv is not None else None
    local_mvrv = fallback_frame["mvrv_z_score"] if "mvrv_z_score" in fallback_frame.columns else None
    series_map["mvrv_z_score"] = _merge_metric(local_mvrv, mvrv, "mvrv_z_score")
    source_modes["mvrv_z_score"] = (
        str(mvrv_mode)
        if mvrv_mode is not None
        else ("local_cache" if local_mvrv is not None and not local_mvrv.empty else "unavailable")
    )

    puell = None
    if coinmetrics is not None and "IssTotUSD" in coinmetrics.columns:
        issuance = coinmetrics.set_index("Date")["IssTotUSD"].dropna().astype(float)
        if not issuance.empty:
            puell = pd.Series(_puell_from_issuance_usd(issuance), name="puell_multiple")
    puell_mode = "coinmetrics_community" if puell is not None else None
    local_puell = fallback_frame["puell_multiple"] if "puell_multiple" in fallback_frame.columns else None
    series_map["puell_multiple"] = _merge_metric(local_puell, puell, "puell_multiple")
    source_modes["puell_multiple"] = (
        str(puell_mode)
        if puell_mode is not None
        else ("local_cache" if local_puell is not None and not local_puell.empty else "unavailable")
    )

    supply_profit = None
    if coinmetrics is not None and "CapMVRVCur" in coinmetrics.columns:
        ratio = coinmetrics.set_index("Date")["CapMVRVCur"].dropna().astype(float)
        if not ratio.empty:
            supply_profit = pd.Series(
                _supply_in_profit_proxy_from_mvrv_ratio(ratio),
                name="supply_in_profit",
            )
    supply_mode = "coinmetrics_community_proxy" if supply_profit is not None else None
    local_supply = fallback_frame["supply_in_profit"] if "supply_in_profit" in fallback_frame.columns else None
    series_map["supply_in_profit"] = _merge_metric(local_supply, supply_profit, "supply_in_profit")
    source_modes["supply_in_profit"] = (
        str(supply_mode)
        if supply_mode is not None
        else ("local_cache" if local_supply is not None and not local_supply.empty else "unavailable")
    )

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
    source_modes["supply_in_loss"] = "derived_from_supply_in_profit"
    out.attrs["source_modes"] = source_modes
    return out
