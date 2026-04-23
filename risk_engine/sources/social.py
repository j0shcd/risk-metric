from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np
import pandas as pd

from ..config import RuntimeConfig
from .common import load_optional_csv, safe_get_json, save_series_csv


YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/channels"


def _merge_history(existing: Optional[pd.Series], snapshot: pd.Series) -> pd.Series:
    if existing is None or existing.empty:
        base = pd.Series(dtype=float)
    else:
        base = existing.astype(float)

    if snapshot is None or snapshot.empty:
        merged = base
    elif base.empty:
        merged = snapshot.astype(float).sort_index()
    else:
        merged = pd.concat([base, snapshot.astype(float)])
        merged = merged[~merged.index.duplicated(keep="last")].sort_index()

    return merged


def _history_path(cfg: RuntimeConfig, kind: str) -> Path:
    if kind == "youtube_interest":
        return cfg.youtube_fallback_csv or (cfg.cache_dir / "youtube_interest.csv")
    if kind == "google_trends_interest":
        return cfg.google_trends_csv or (cfg.cache_dir / "google_trends_interest.csv")
    if kind == "coinbase_app_rank":
        return cfg.coinbase_rank_csv or (cfg.cache_dir / "coinbase_app_rank.csv")
    raise ValueError(f"Unknown history kind: {kind}")


def _update_history_with_snapshot(
    path: Path,
    value_column: str,
    snapshot: pd.Series,
) -> pd.Series:
    existing = load_optional_csv(path, value_column=value_column)
    merged = _merge_history(existing, snapshot)
    if not merged.empty:
        save_series_csv(path, merged, value_column=value_column)
    return merged


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


def _load_youtube_interest(cfg: RuntimeConfig) -> pd.Series:
    path = _history_path(cfg, "youtube_interest")
    snapshot = _fetch_youtube_interest(cfg)
    return _update_history_with_snapshot(path=path, value_column="youtube_interest", snapshot=snapshot)


def _coerce_timestamp(raw: Any) -> Optional[pd.Timestamp]:
    if raw is None:
        return None
    parsed = pd.to_datetime(raw, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed.tz_convert(None).normalize()


def _coerce_numeric(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        nums = pd.to_numeric(pd.Series(raw), errors="coerce").dropna()
        if nums.empty:
            return None
        return float(nums.mean())
    value = pd.to_numeric(raw, errors="coerce")
    if pd.isna(value):
        return None
    return float(value)


def _extract_rows(payload: Any) -> Iterable[dict]:
    if isinstance(payload, dict):
        for key in ("data", "points", "timelineData", "timeline", "rows", "values", "series"):
            value = payload.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        yield item
        for value in payload.values():
            if isinstance(value, dict):
                yield from _extract_rows(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        yield from _extract_rows(item)
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                yield from _extract_rows(item)


def _parse_google_trends_series(payload: Any) -> pd.Series:
    rows = []
    for row in _extract_rows(payload):
        timestamp = None
        value = None

        for time_key in ("date", "time", "timestamp", "datetime", "startTime", "week"):
            timestamp = _coerce_timestamp(row.get(time_key))
            if timestamp is not None:
                break

        for value_key in ("value", "interest", "score", "index", "popularity"):
            value = _coerce_numeric(row.get(value_key))
            if value is not None:
                break

        if timestamp is None or value is None:
            continue

        rows.append((timestamp, value))

    if not rows:
        return pd.Series(dtype=float)

    frame = pd.DataFrame(rows, columns=["Date", "google_trends_interest"])
    frame = frame.drop_duplicates(subset=["Date"], keep="last").sort_values("Date")
    return frame.set_index("Date")["google_trends_interest"]


def _fetch_google_trends_interest(cfg: RuntimeConfig) -> pd.Series:
    if not cfg.google_trends_api_key or not cfg.google_trends_api_url:
        return pd.Series(dtype=float)

    terms = cfg.google_trends_terms or ["bitcoin"]
    payload = safe_get_json(
        url=cfg.google_trends_api_url,
        timeout_seconds=cfg.request_timeout_seconds,
        headers={"X-Goog-Api-Key": cfg.google_trends_api_key},
        params={
            "terms": ",".join(terms),
            "timeframe": "today 5-y",
        },
    )
    if payload is None:
        return pd.Series(dtype=float)

    return _parse_google_trends_series(payload)


def _load_google_trends_interest(cfg: RuntimeConfig) -> pd.Series:
    path = _history_path(cfg, "google_trends_interest")
    snapshot = _fetch_google_trends_interest(cfg)
    return _update_history_with_snapshot(
        path=path,
        value_column="google_trends_interest",
        snapshot=snapshot,
    )


def _fetch_coinbase_rank_snapshot(cfg: RuntimeConfig) -> pd.Series:
    if not cfg.enable_coinbase_app_rank:
        return pd.Series(dtype=float)

    url = f"https://rss.marketingtools.apple.com/api/v2/{cfg.apple_app_store_country}/apps/top-free/200/finance.json"
    payload = safe_get_json(url=url, timeout_seconds=cfg.request_timeout_seconds)
    if payload is None:
        return pd.Series(dtype=float)

    feed = payload.get("feed", {})
    results = feed.get("results", [])
    if not results:
        return pd.Series(dtype=float)

    rank = None
    for i, app in enumerate(results, start=1):
        app_id = str(app.get("id", ""))
        app_name = str(app.get("name", "")).lower()
        if app_id == str(cfg.coinbase_ios_app_id) or "coinbase" in app_name:
            rank = i
            break

    if rank is None:
        return pd.Series(dtype=float)

    updated_raw = feed.get("updated")
    timestamp = pd.Timestamp.utcnow().normalize().tz_localize(None)
    if updated_raw:
        parsed = pd.to_datetime(updated_raw, utc=True, errors="coerce")
        if pd.notna(parsed):
            timestamp = parsed.tz_convert(None).normalize()

    return pd.Series([float(rank)], index=[timestamp], name="coinbase_app_rank")


def _load_coinbase_app_rank(cfg: RuntimeConfig) -> pd.Series:
    if not cfg.enable_coinbase_app_rank:
        return pd.Series(dtype=float)

    path = _history_path(cfg, "coinbase_app_rank")
    snapshot = _fetch_coinbase_rank_snapshot(cfg)
    rank_series = _update_history_with_snapshot(path=path, value_column="coinbase_app_rank", snapshot=snapshot)
    if rank_series.empty:
        return pd.Series(dtype=float)

    # Lower rank means hotter market interest. Keep raw value as negative rank.
    transformed = -1.0 * rank_series.astype(float)
    transformed.name = "coinbase_app_rank_proxy"
    return transformed


def load_social_metrics(cfg: RuntimeConfig, index: pd.DatetimeIndex) -> pd.DataFrame:
    out = pd.DataFrame(index=index)

    youtube = _load_youtube_interest(cfg)

    if youtube.empty:
        out["youtube_interest"] = np.nan
    else:
        out["youtube_interest"] = youtube.reindex(index)

    google_trends = _load_google_trends_interest(cfg)
    if google_trends.empty:
        out["google_trends_interest"] = np.nan
    else:
        out["google_trends_interest"] = google_trends.reindex(index)

    coinbase = _load_coinbase_app_rank(cfg)
    if coinbase.empty:
        out["coinbase_app_rank_proxy"] = np.nan
    else:
        out["coinbase_app_rank_proxy"] = coinbase.reindex(index)

    return out
