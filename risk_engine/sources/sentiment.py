from __future__ import annotations

import pandas as pd

from ..config import RuntimeConfig
from .common import load_optional_csv, safe_get_json, save_series_csv


def _fetch_alternative_fear_greed(cfg: RuntimeConfig) -> pd.Series:
    if not cfg.refresh_api_sources:
        return pd.Series(dtype=float)
    payload = safe_get_json(
        url="https://api.alternative.me/fng/",
        timeout_seconds=cfg.request_timeout_seconds,
        params={"limit": 0, "format": "json"},
    )

    if payload is None:
        return pd.Series(dtype=float)

    data = payload.get("data", [])
    rows = []
    for item in data:
        if "timestamp" not in item or "value" not in item:
            continue
        dt = pd.to_datetime(int(item["timestamp"]), unit="s").tz_localize(None).normalize()
        rows.append((dt, float(item["value"])))

    if not rows:
        return pd.Series(dtype=float)

    frame = pd.DataFrame(rows, columns=["Date", "fear_greed_index"]).drop_duplicates(subset=["Date"]).sort_values("Date")
    return frame.set_index("Date")["fear_greed_index"]


def load_fear_greed_index(cfg: RuntimeConfig, index: pd.DatetimeIndex) -> pd.Series:
    fallback_path = cfg.cache_dir / "fear_greed_index.csv"

    series = _fetch_alternative_fear_greed(cfg)
    source_mode = "alternative_me_api" if not series.empty else None
    if series.empty:
        fallback = load_optional_csv(fallback_path, value_column="fear_greed_index")
        series = fallback if fallback is not None else pd.Series(dtype=float)
        source_mode = "local_cache" if fallback is not None and not fallback.empty else "unavailable"
    else:
        save_series_csv(fallback_path, series, value_column="fear_greed_index")

    if series.empty:
        out = pd.Series(index=index, dtype=float, name="fear_greed_index")
        out.attrs["source_mode"] = source_mode
        return out

    out = series.reindex(index).rename("fear_greed_index")
    out.attrs["source_mode"] = source_mode
    return out
