from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from ..config import RuntimeConfig
from .common import load_optional_csv, safe_get_json


YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/channels"


def _fetch_youtube_interest(cfg: RuntimeConfig) -> pd.Series:
    if not cfg.youtube_api_key or not cfg.youtube_channel_ids:
        return pd.Series(dtype=float)

    payload = safe_get_json(
        url=YOUTUBE_API_URL,
        timeout_seconds=cfg.request_timeout_seconds,
        params={
            "part": "statistics",
            "id": ",".join(cfg.youtube_channel_ids),
            "key": cfg.youtube_api_key,
            "maxResults": 50,
        },
    )

    if payload is None:
        return pd.Series(dtype=float)

    items = payload.get("items", [])
    if not items:
        return pd.Series(dtype=float)

    total_subscribers = 0.0
    total_views = 0.0
    for item in items:
        stats = item.get("statistics", {})
        total_subscribers += float(stats.get("subscriberCount", 0.0))
        total_views += float(stats.get("viewCount", 0.0))

    interest = np.log1p(total_subscribers) + 0.25 * np.log1p(total_views)
    today = pd.Timestamp.utcnow().normalize().tz_localize(None)
    return pd.Series([interest], index=[today], name="youtube_interest")


def _load_google_trends_proxy(cfg: RuntimeConfig) -> pd.Series:
    # The official Google Trends API is alpha-gated; use local fallback data for v1.
    series = load_optional_csv(cfg.google_trends_csv, value_column="google_trends_interest")
    if series is None:
        return pd.Series(dtype=float)
    return series


def _load_coinbase_app_rank(cfg: RuntimeConfig) -> pd.Series:
    if not cfg.enable_coinbase_app_rank:
        return pd.Series(dtype=float)

    rank_series = load_optional_csv(cfg.coinbase_rank_csv, value_column="coinbase_app_rank")
    if rank_series is None or rank_series.empty:
        return pd.Series(dtype=float)

    # Lower rank means hotter market interest. Keep raw value as negative rank.
    transformed = -1.0 * rank_series.astype(float)
    transformed.name = "coinbase_app_rank_proxy"
    return transformed


def load_social_metrics(cfg: RuntimeConfig, index: pd.DatetimeIndex) -> pd.DataFrame:
    out = pd.DataFrame(index=index)

    youtube = _fetch_youtube_interest(cfg)
    if youtube.empty:
        fallback = load_optional_csv(cfg.youtube_fallback_csv, value_column="youtube_interest")
        youtube = fallback if fallback is not None else pd.Series(dtype=float)

    if youtube.empty:
        out["youtube_interest"] = np.nan
    else:
        out["youtube_interest"] = youtube.reindex(index).ffill()

    google_trends = _load_google_trends_proxy(cfg)
    if google_trends.empty:
        out["google_trends_interest"] = np.nan
    else:
        out["google_trends_interest"] = google_trends.reindex(index).ffill()

    coinbase = _load_coinbase_app_rank(cfg)
    if coinbase.empty:
        out["coinbase_app_rank_proxy"] = np.nan
    else:
        out["coinbase_app_rank_proxy"] = coinbase.reindex(index).ffill()

    return out
