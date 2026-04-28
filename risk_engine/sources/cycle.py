from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

from ..config import RuntimeConfig
from .common import load_optional_csv, safe_get_json, safe_get_text, save_series_csv


def _market_store_path(cfg: RuntimeConfig) -> Path:
    return cfg.coingecko_btc_market_csv or (cfg.cache_dir / "btc_market_coingecko.csv")


def _wiki_store_path(cfg: RuntimeConfig) -> Path:
    return cfg.wikipedia_pageviews_csv or (cfg.cache_dir / "wikipedia_pageviews_btc.csv")


def _reddit_store_path(cfg: RuntimeConfig) -> Path:
    return cfg.reddit_posts_csv or (cfg.cache_dir / "reddit_post_volume.csv")


def _fred_store_path(cfg: RuntimeConfig, series_id: str) -> Path:
    mapping = {
        "DTWEXBGS": cfg.fred_dxy_csv,
        "DFII10": cfg.fred_real_yield_csv,
        "WALCL": cfg.fred_walcl_csv,
        "RRPONTSYD": cfg.fred_rrp_csv,
    }
    configured = mapping.get(series_id)
    if configured is not None:
        return configured
    return cfg.cache_dir / f"fred_{series_id.lower()}.csv"


def _merge_series(existing: Optional[pd.Series], updates: Optional[pd.Series], name: str) -> pd.Series:
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


def _parse_coingecko_market_chart(payload: dict) -> Tuple[pd.Series, pd.Series]:
    market = payload.get("market_caps", [])
    prices = payload.get("prices", [])
    volumes = payload.get("total_volumes", [])
    if not prices:
        return pd.Series(dtype=float, name="btc_price_usd"), pd.Series(dtype=float, name="btc_volume_usd")

    price_rows = []
    for unix_ms, value in prices:
        date = pd.to_datetime(unix_ms, unit="ms").tz_localize(None).normalize()
        price_rows.append((date, float(value)))

    volume_rows = []
    for unix_ms, value in volumes:
        date = pd.to_datetime(unix_ms, unit="ms").tz_localize(None).normalize()
        volume_rows.append((date, float(value)))

    # `market_caps` is not consumed directly, but the payload key is checked to avoid malformed data.
    if market is None:
        return pd.Series(dtype=float, name="btc_price_usd"), pd.Series(dtype=float, name="btc_volume_usd")

    price = (
        pd.DataFrame(price_rows, columns=["Date", "btc_price_usd"])
        .drop_duplicates(subset=["Date"], keep="last")
        .sort_values("Date")
        .set_index("Date")["btc_price_usd"]
    )
    volume = (
        pd.DataFrame(volume_rows, columns=["Date", "btc_volume_usd"])
        .drop_duplicates(subset=["Date"], keep="last")
        .sort_values("Date")
        .set_index("Date")["btc_volume_usd"]
    )
    return price, volume


def _parse_local_btc_volume(cfg: RuntimeConfig) -> pd.Series:
    btc_path = cfg.data_dir / "btc_daily.csv"
    if not btc_path.exists():
        return pd.Series(dtype=float, name="btc_volume_usd")

    frame = pd.read_csv(btc_path)
    if "Date" not in frame.columns or "Vol." not in frame.columns:
        return pd.Series(dtype=float, name="btc_volume_usd")

    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce").dt.tz_localize(None)
    frame = frame.dropna(subset=["Date"]).copy()

    def parse_volume(value: object) -> float:
        if value is None:
            return float("nan")
        text = str(value).strip().replace(",", "")
        if not text:
            return float("nan")
        multiplier = 1.0
        suffix = text[-1].upper()
        if suffix in {"K", "M", "B", "T"}:
            text = text[:-1]
            multiplier = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}[suffix]
        try:
            return float(text) * multiplier
        except Exception:
            return float("nan")

    frame["btc_volume_usd"] = frame["Vol."].map(parse_volume)
    series = pd.Series(frame["btc_volume_usd"].values, index=frame["Date"], name="btc_volume_usd")
    series = series[~series.index.duplicated(keep="last")].sort_index()
    return series.astype(float)


def load_cycle_market_context(
    cfg: RuntimeConfig,
    index: pd.DatetimeIndex,
    btc_price: pd.Series,
    social_frame: pd.DataFrame,
) -> pd.DataFrame:
    out = pd.DataFrame(index=index)
    source_modes: Dict[str, str] = {}

    market_store = _market_store_path(cfg)
    local_price = load_optional_csv(market_store, value_column="btc_price_usd")
    local_volume = load_optional_csv(market_store, value_column="btc_volume_usd")

    fetched_price = pd.Series(dtype=float, name="btc_price_usd")
    fetched_volume = pd.Series(dtype=float, name="btc_volume_usd")
    payload = safe_get_json(
        url="https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
        timeout_seconds=cfg.request_timeout_seconds,
        params={"vs_currency": "usd", "days": "max"},
    )
    if payload is not None:
        fetched_price, fetched_volume = _parse_coingecko_market_chart(payload)

    merged_price = _merge_series(local_price, fetched_price, "btc_price_usd")
    merged_volume = _merge_series(local_volume, fetched_volume, "btc_volume_usd")

    if not merged_price.empty or not merged_volume.empty:
        export = pd.DataFrame(index=merged_price.index.union(merged_volume.index))
        export["btc_price_usd"] = merged_price.reindex(export.index)
        export["btc_volume_usd"] = merged_volume.reindex(export.index)
        export = export.sort_index()
        export.index.name = "Date"
        market_store.parent.mkdir(parents=True, exist_ok=True)
        export.reset_index().to_csv(market_store, index=False)

    volume_local_fallback = _parse_local_btc_volume(cfg)
    merged_volume = _merge_series(merged_volume, volume_local_fallback, "btc_volume_usd")

    # Keep project BTC price as canonical for consistency with existing outputs.
    out["btc_price"] = btc_price.reindex(index)
    source_modes["cycle::btc_price"] = "local_csv"

    out["btc_volume_usd"] = merged_volume.reindex(index)
    if not fetched_volume.empty:
        source_modes["cycle::btc_volume_usd"] = "coingecko_free_api"
    elif local_volume is not None and not local_volume.empty:
        source_modes["cycle::btc_volume_usd"] = "local_cache"
    elif not volume_local_fallback.empty:
        source_modes["cycle::btc_volume_usd"] = "local_csv"
    else:
        source_modes["cycle::btc_volume_usd"] = "unavailable"

    out["google_trends_interest"] = social_frame.get("google_trends_interest", pd.Series(index=index, dtype=float))
    source_modes["cycle::google_trends_interest"] = str(
        social_frame.attrs.get("source_modes", {}).get("google_trends_interest", "unknown")
    )

    wiki_store = _wiki_store_path(cfg)
    local_wiki = load_optional_csv(wiki_store, value_column="wikipedia_pageviews")
    wiki_start = max(pd.Timestamp("2015-07-01"), pd.Timestamp(index.min().date()))
    wiki_end = pd.Timestamp(index.max().date())
    wiki_fetched = _fetch_wikipedia_pageviews(cfg, start=wiki_start, end=wiki_end)
    wiki_merged = _merge_series(local_wiki, wiki_fetched, "wikipedia_pageviews")
    if not wiki_merged.empty:
        save_series_csv(wiki_store, wiki_merged, value_column="wikipedia_pageviews")
    out["wikipedia_pageviews"] = wiki_merged.reindex(index)
    if not wiki_fetched.empty:
        source_modes["cycle::wikipedia_pageviews"] = "wikimedia_api"
    elif local_wiki is not None and not local_wiki.empty:
        source_modes["cycle::wikipedia_pageviews"] = "local_cache"
    else:
        source_modes["cycle::wikipedia_pageviews"] = "unavailable"

    reddit_store = _reddit_store_path(cfg)
    local_reddit = load_optional_csv(reddit_store, value_column="reddit_post_volume")
    reddit_fetched = _fetch_reddit_post_volume(cfg, start=pd.Timestamp(index.min().date()), end=pd.Timestamp(index.max().date()))
    reddit_merged = _merge_series(local_reddit, reddit_fetched, "reddit_post_volume")
    if not reddit_merged.empty:
        save_series_csv(reddit_store, reddit_merged, value_column="reddit_post_volume")
    out["reddit_post_volume"] = reddit_merged.reindex(index)
    if not reddit_fetched.empty:
        source_modes["cycle::reddit_post_volume"] = "pushshift_api"
    elif local_reddit is not None and not local_reddit.empty:
        source_modes["cycle::reddit_post_volume"] = "local_cache"
    else:
        source_modes["cycle::reddit_post_volume"] = "unavailable"

    macro_frame, macro_modes = _load_macro_series(cfg, index=index)
    out = pd.concat([out, macro_frame], axis=1)
    source_modes.update(macro_modes)
    out.attrs["source_modes"] = source_modes
    return out


def _fetch_wikipedia_pageviews(cfg: RuntimeConfig, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    start_token = start.strftime("%Y%m%d00")
    end_token = end.strftime("%Y%m%d00")
    url = (
        "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
        f"en.wikipedia/all-access/all-agents/Bitcoin/daily/{start_token}/{end_token}"
    )
    payload = safe_get_json(url=url, timeout_seconds=cfg.request_timeout_seconds)
    if payload is None:
        return pd.Series(dtype=float, name="wikipedia_pageviews")

    rows = []
    for item in payload.get("items", []):
        ts = item.get("timestamp")
        views = item.get("views")
        if ts is None or views is None:
            continue
        parsed = pd.to_datetime(str(ts)[:8], format="%Y%m%d", errors="coerce")
        if pd.isna(parsed):
            continue
        rows.append((parsed.tz_localize(None), float(views)))

    if not rows:
        return pd.Series(dtype=float, name="wikipedia_pageviews")
    frame = pd.DataFrame(rows, columns=["Date", "wikipedia_pageviews"]).drop_duplicates(subset=["Date"], keep="last")
    frame = frame.sort_values("Date")
    return frame.set_index("Date")["wikipedia_pageviews"]


def _parse_reddit_agg(payload: dict) -> pd.Series:
    aggs = payload.get("aggs", {})
    created = aggs.get("created_utc", []) if isinstance(aggs, dict) else []
    rows = []
    for item in created:
        key = item.get("key")
        count = item.get("doc_count")
        if key is None or count is None:
            continue
        date = pd.to_datetime(int(key), unit="s", errors="coerce")
        if pd.isna(date):
            continue
        rows.append((date.tz_localize(None).normalize(), float(count)))

    if not rows:
        return pd.Series(dtype=float, name="reddit_post_volume")
    frame = pd.DataFrame(rows, columns=["Date", "reddit_post_volume"]).drop_duplicates(subset=["Date"], keep="last")
    frame = frame.sort_values("Date")
    return frame.set_index("Date")["reddit_post_volume"]


def _fetch_reddit_post_volume(cfg: RuntimeConfig, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    if start > end:
        return pd.Series(dtype=float, name="reddit_post_volume")

    endpoint = "https://api.pushshift.io/reddit/search/submission/"
    series_parts = []
    for subreddit in cfg.reddit_subreddits or ["Bitcoin"]:
        payload = safe_get_json(
            url=endpoint,
            timeout_seconds=cfg.request_timeout_seconds,
            params={
                "subreddit": subreddit,
                "after": int(start.timestamp()),
                "before": int((end + pd.Timedelta(days=1)).timestamp()),
                "size": 0,
                "aggs": "created_utc",
                "frequency": "day",
            },
        )
        if payload is None:
            continue
        part = _parse_reddit_agg(payload)
        if part.empty:
            continue
        series_parts.append(part)

    if not series_parts:
        return pd.Series(dtype=float, name="reddit_post_volume")
    combined = pd.concat(series_parts, axis=1).sum(axis=1, min_count=1)
    combined.name = "reddit_post_volume"
    return combined.sort_index()


def _fetch_fred_series(cfg: RuntimeConfig, series_id: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    text = safe_get_text(
        url="https://fred.stlouisfed.org/graph/fredgraph.csv",
        timeout_seconds=cfg.request_timeout_seconds,
        params={
            "id": series_id,
            "cosd": start.strftime("%Y-%m-%d"),
            "coed": end.strftime("%Y-%m-%d"),
        },
    )
    if text is None:
        return pd.Series(dtype=float, name=series_id)

    try:
        frame = pd.read_csv(StringIO(text))
    except Exception:
        return pd.Series(dtype=float, name=series_id)

    if "DATE" not in frame.columns or series_id not in frame.columns:
        return pd.Series(dtype=float, name=series_id)

    frame["DATE"] = pd.to_datetime(frame["DATE"], errors="coerce").dt.tz_localize(None)
    frame[series_id] = pd.to_numeric(frame[series_id], errors="coerce")
    frame = frame.dropna(subset=["DATE"]).sort_values("DATE")
    frame = frame.drop_duplicates(subset=["DATE"], keep="last")
    if frame.empty:
        return pd.Series(dtype=float, name=series_id)
    return pd.Series(frame[series_id].values, index=frame["DATE"], name=series_id)


def _load_macro_series(cfg: RuntimeConfig, index: pd.DatetimeIndex) -> Tuple[pd.DataFrame, Dict[str, str]]:
    start = pd.Timestamp(index.min().date())
    end = pd.Timestamp(index.max().date())
    mode_map: Dict[str, str] = {}
    out = pd.DataFrame(index=index)

    mapping = {
        "DTWEXBGS": "dxy",
        "DFII10": "real_yield_10y",
        "WALCL": "fed_balance_sheet",
        "RRPONTSYD": "reverse_repo_balance",
    }

    series_store: Dict[str, pd.Series] = {}
    for fred_id, name in mapping.items():
        path = _fred_store_path(cfg, fred_id)
        local = load_optional_csv(path, value_column=name)
        fetched = _fetch_fred_series(cfg, fred_id, start=start, end=end)
        if not fetched.empty:
            fetched.name = name
        merged = _merge_series(local, fetched.rename(name) if not fetched.empty else None, name)
        if not merged.empty:
            save_series_csv(path, merged, value_column=name)
        series_store[name] = merged
        if not fetched.empty:
            mode_map[f"cycle::{name}"] = "fred_graph_csv"
        elif local is not None and not local.empty:
            mode_map[f"cycle::{name}"] = "local_cache"
        else:
            mode_map[f"cycle::{name}"] = "unavailable"

    out["dxy"] = series_store["dxy"].reindex(index)
    out["real_yield_10y"] = series_store["real_yield_10y"].reindex(index)
    out["fed_balance_sheet"] = series_store["fed_balance_sheet"].reindex(index)
    out["reverse_repo_balance"] = series_store["reverse_repo_balance"].reindex(index)

    out["net_liquidity"] = out["fed_balance_sheet"] - out["reverse_repo_balance"]
    components_available = out[["fed_balance_sheet", "reverse_repo_balance"]].notna().all(axis=1)
    out.loc[~components_available, "net_liquidity"] = np.nan
    if (mode_map.get("cycle::fed_balance_sheet") == "fred_graph_csv") or (
        mode_map.get("cycle::reverse_repo_balance") == "fred_graph_csv"
    ):
        mode_map["cycle::net_liquidity"] = "derived_from_fred_graph_csv"
    elif (mode_map.get("cycle::fed_balance_sheet") == "local_cache") and (
        mode_map.get("cycle::reverse_repo_balance") == "local_cache"
    ):
        mode_map["cycle::net_liquidity"] = "derived_from_local_cache"
    else:
        mode_map["cycle::net_liquidity"] = "unavailable"

    return out, mode_map
