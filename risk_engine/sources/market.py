from __future__ import annotations

from typing import Optional

import pandas as pd

from ..config import RuntimeConfig
from .common import load_optional_csv, safe_get_json, save_series_csv


def load_btc_price(cfg: RuntimeConfig) -> pd.Series:
    btc_path = cfg.data_dir / "btc_daily.csv"
    if not btc_path.exists():
        raise FileNotFoundError(f"Missing BTC data file: {btc_path}")

    frame = pd.read_csv(btc_path, parse_dates=["Date"])
    frame["Date"] = pd.to_datetime(frame["Date"]).dt.tz_localize(None)
    prices = frame.set_index("Date")["Price"].astype(float).sort_index()

    if cfg.start_date:
        prices = prices[prices.index >= pd.Timestamp(cfg.start_date)]
    if cfg.end_date:
        prices = prices[prices.index <= pd.Timestamp(cfg.end_date)]

    return prices


def _parse_cmc_global_market_cap(payload: dict) -> Optional[pd.Series]:
    try:
        quotes = payload["data"]["quotes"]
    except Exception:
        return None

    rows = []
    for quote in quotes:
        timestamp = pd.to_datetime(quote["timestamp"]).tz_localize(None).normalize()
        quote_map = quote.get("quote", {})
        usd_payload = quote_map.get("USD")
        if usd_payload is None and quote_map:
            usd_payload = next(iter(quote_map.values()))
        if not usd_payload:
            continue
        total_market_cap = usd_payload.get("total_market_cap")
        if total_market_cap is None:
            continue
        rows.append((timestamp, float(total_market_cap)))

    if not rows:
        return None

    frame = pd.DataFrame(rows, columns=["Date", "total_market_cap"]).drop_duplicates(subset=["Date"]).sort_values("Date")
    return frame.set_index("Date")["total_market_cap"]


def _fetch_cmc_total_market_cap(cfg: RuntimeConfig, start: pd.Timestamp, end: pd.Timestamp) -> Optional[pd.Series]:
    if not cfg.refresh_api_sources:
        return None
    if not cfg.enable_paid_sources:
        return None
    if not cfg.cmc_api_key:
        return None

    payload = safe_get_json(
        url="https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/historical",
        timeout_seconds=cfg.request_timeout_seconds,
        headers={"X-CMC_PRO_API_KEY": cfg.cmc_api_key},
        params={
            "time_start": start.strftime("%Y-%m-%d"),
            "time_end": end.strftime("%Y-%m-%d"),
            "interval": "daily",
            "convert": "USD",
        },
    )

    if payload is None:
        return None

    return _parse_cmc_global_market_cap(payload)


def _fetch_coingecko_total_market_cap(cfg: RuntimeConfig) -> Optional[pd.Series]:
    if not cfg.refresh_api_sources:
        return None
    if not cfg.enable_paid_sources:
        return None
    if not cfg.coingecko_api_key:
        return None

    payload = safe_get_json(
        url="https://pro-api.coingecko.com/api/v3/global/market_cap_chart",
        timeout_seconds=cfg.request_timeout_seconds,
        headers={"x-cg-pro-api-key": cfg.coingecko_api_key},
        params={"days": "max", "vs_currency": "usd"},
    )

    if payload is None:
        return None

    try:
        points = payload["market_cap_chart"]["market_cap"]
    except Exception:
        return None

    rows = []
    for unix_ms, value in points:
        timestamp = pd.to_datetime(unix_ms, unit="ms").tz_localize(None).normalize()
        rows.append((timestamp, float(value)))

    if not rows:
        return None

    frame = pd.DataFrame(rows, columns=["Date", "total_market_cap"]).drop_duplicates(subset=["Date"]).sort_values("Date")
    return frame.set_index("Date")["total_market_cap"]


def _fetch_coingecko_global_latest(cfg: RuntimeConfig) -> Optional[pd.Series]:
    if not cfg.refresh_api_sources:
        return None
    payload = safe_get_json(
        url="https://api.coingecko.com/api/v3/global",
        timeout_seconds=cfg.request_timeout_seconds,
    )

    if payload is None:
        return None

    try:
        data = payload["data"]
        usd_cap = data["total_market_cap"]["usd"]
    except Exception:
        return None

    updated_at = data.get("updated_at")
    if updated_at is None:
        timestamp = pd.Timestamp.utcnow().normalize()
    else:
        timestamp = pd.to_datetime(int(updated_at), unit="s").tz_localize(None).normalize()

    return pd.Series([float(usd_cap)], index=[timestamp], name="total_market_cap")


def _merge_series(base: Optional[pd.Series], updates: Optional[pd.Series]) -> pd.Series:
    if base is None or base.empty:
        return updates.copy() if updates is not None else pd.Series(dtype=float, name="total_market_cap")
    if updates is None or updates.empty:
        return base.copy()

    merged = pd.concat([base, updates])
    merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    merged.name = "total_market_cap"
    return merged


def load_total_market_cap(cfg: RuntimeConfig, index: pd.DatetimeIndex) -> pd.Series:
    fallback_path = cfg.total_marketcap_csv or (cfg.cache_dir / "total_marketcap.csv")

    # 1) Local fallback
    local_series = load_optional_csv(fallback_path, value_column="total_market_cap")

    # 2) CMC (preferred when key is present)
    fetched = None
    fetched_mode = None
    start = pd.Timestamp(index.min().date())
    end = pd.Timestamp(index.max().date())
    fetched = _fetch_cmc_total_market_cap(cfg, start=start, end=end)
    if fetched is not None:
        fetched_mode = "cmc_api"

    # 3) CoinGecko Pro fallback
    if fetched is None:
        fetched = _fetch_coingecko_total_market_cap(cfg)
        if fetched is not None:
            fetched_mode = "coingecko_pro"

    # 4) CoinGecko free global latest snapshot fallback (append-only style)
    if fetched is None:
        fetched = _fetch_coingecko_global_latest(cfg)
        if fetched is not None:
            fetched_mode = "coingecko_global_latest"

    if fetched is not None:
        merged = _merge_series(local_series, fetched)
        save_series_csv(fallback_path, merged, value_column="total_market_cap")
        source_mode = str(fetched_mode or "api")
    else:
        merged = local_series if local_series is not None else pd.Series(dtype=float, name="total_market_cap")
        source_mode = "local_cache" if local_series is not None and not local_series.empty else "unavailable"

    if merged.empty:
        out = pd.Series(index=index, dtype=float, name="total_market_cap")
        out.attrs["source_mode"] = source_mode
        return out

    merged = merged[(merged.index >= start) & (merged.index <= end)]
    merged = merged.reindex(index)
    merged.name = "total_market_cap"
    merged.attrs["source_mode"] = source_mode
    return merged
