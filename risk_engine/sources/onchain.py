from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd
import requests

from ..config import RuntimeConfig

MVRV_RATIO_Z_PROXY = "mvrv_ratio_z_proxy"
PROFITABILITY_DISPLAY_PROXY = "mvrv_implied_profitability_proxy"
CORE_METRICS = [MVRV_RATIO_Z_PROXY, "puell_multiple", PROFITABILITY_DISPLAY_PROXY]


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


def _mvrv_ratio_z_proxy(ratio: pd.Series) -> pd.Series:
    mean = ratio.expanding(min_periods=365).mean()
    std = ratio.expanding(min_periods=365).std(ddof=0).replace({0.0: np.nan})
    return (ratio - mean) / std


def _puell_from_issuance_usd(issuance_usd: pd.Series) -> pd.Series:
    denom = issuance_usd.rolling(365, min_periods=90).mean().replace({0.0: np.nan})
    return issuance_usd / denom


def _profitability_display_proxy_from_mvrv_ratio(mvrv_ratio: pd.Series) -> pd.Series:
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
            mvrv = pd.Series(_mvrv_ratio_z_proxy(ratio), name=MVRV_RATIO_Z_PROXY)
    mvrv_mode = "coinmetrics_community" if mvrv is not None else None
    local_mvrv = (
        fallback_frame[MVRV_RATIO_Z_PROXY]
        if MVRV_RATIO_Z_PROXY in fallback_frame.columns
        else fallback_frame.get("mvrv_z_score")
    )
    series_map[MVRV_RATIO_Z_PROXY] = _merge_metric(local_mvrv, mvrv, MVRV_RATIO_Z_PROXY)
    source_modes[MVRV_RATIO_Z_PROXY] = (
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

    profitability_proxy = None
    if coinmetrics is not None and "CapMVRVCur" in coinmetrics.columns:
        ratio = coinmetrics.set_index("Date")["CapMVRVCur"].dropna().astype(float)
        if not ratio.empty:
            profitability_proxy = pd.Series(
                _profitability_display_proxy_from_mvrv_ratio(ratio),
                name=PROFITABILITY_DISPLAY_PROXY,
            )
    profitability_mode = "coinmetrics_community_proxy" if profitability_proxy is not None else None
    local_profitability = (
        fallback_frame[PROFITABILITY_DISPLAY_PROXY]
        if PROFITABILITY_DISPLAY_PROXY in fallback_frame.columns
        else fallback_frame.get("supply_in_profit")
    )
    series_map[PROFITABILITY_DISPLAY_PROXY] = _merge_metric(
        local_profitability,
        profitability_proxy,
        PROFITABILITY_DISPLAY_PROXY,
    )
    source_modes[PROFITABILITY_DISPLAY_PROXY] = (
        str(profitability_mode)
        if profitability_mode is not None
        else ("local_cache" if local_profitability is not None and not local_profitability.empty else "unavailable")
    )

    # Keep unknown local columns if user stored additional on-chain metrics.
    legacy_columns = {"mvrv_z_score", "supply_in_profit", "supply_in_loss"}
    for col in fallback_frame.columns:
        if col not in series_map and col not in legacy_columns:
            series_map[col] = fallback_frame[col].astype(float)

    _save_onchain_store(store_path, series_map)

    out = pd.DataFrame(index=index)
    for name in CORE_METRICS:
        series = series_map.get(name, pd.Series(dtype=float))
        if series.empty:
            out[name] = np.nan
            continue
        out[name] = series.reindex(index)

    out.attrs["source_modes"] = source_modes
    return out
