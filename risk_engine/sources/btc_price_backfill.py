from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd
import requests

from ..config import RuntimeConfig


BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
COINGECKO_MARKET_CHART_URL = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
_BTC_DAILY_COLUMNS = ["Date", "Open", "High", "Low", "Price", "Vol.", "Change %"]


def _yesterday_utc() -> pd.Timestamp:
    return pd.Timestamp.now("UTC").tz_localize(None).normalize() - pd.Timedelta(days=1)


def _read_existing_btc_daily(csv_path: Path) -> pd.DataFrame:
    frame = pd.read_csv(csv_path, parse_dates=["Date"])
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce").dt.tz_localize(None)
    frame = frame.dropna(subset=["Date"]).copy()

    for column in ["Open", "High", "Low", "Price", "Vol.", "Change %"]:
        if column not in frame.columns:
            frame[column] = pd.NA
        frame[column] = pd.to_numeric(frame[column].astype(str).str.replace(",", "", regex=False), errors="coerce")

    frame = frame[_BTC_DAILY_COLUMNS]
    frame = frame.dropna(subset=["Date"]).drop_duplicates(subset=["Date"], keep="last").sort_values("Date")
    return frame


def _fetch_binance_klines_page(
    symbol: str,
    interval: str,
    start_time_ms: int,
    timeout_seconds: int,
    limit: int = 1000,
) -> List[list]:
    try:
        response = requests.get(
            BINANCE_KLINES_URL,
            params={
                "symbol": symbol,
                "interval": interval,
                "startTime": start_time_ms,
                "limit": limit,
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []

    if not isinstance(payload, list):
        return []
    return payload


def _klines_to_frame(klines: List[list]) -> pd.DataFrame:
    if not klines:
        return pd.DataFrame(columns=_BTC_DAILY_COLUMNS)

    rows = []
    for row in klines:
        if not isinstance(row, list) or len(row) < 6:
            continue
        try:
            date = pd.to_datetime(int(row[0]), unit="ms", utc=True).tz_convert(None).normalize()
            open_px = float(row[1])
            high_px = float(row[2])
            low_px = float(row[3])
            close_px = float(row[4])
            volume = float(row[5])
        except Exception:
            continue

        if open_px == 0:
            change_pct = 0.0
        else:
            change_pct = ((close_px / open_px) - 1.0) * 100.0
        rows.append((date, open_px, high_px, low_px, close_px, volume, round(change_pct, 2)))

    if not rows:
        return pd.DataFrame(columns=_BTC_DAILY_COLUMNS)

    return pd.DataFrame(rows, columns=_BTC_DAILY_COLUMNS).drop_duplicates(subset=["Date"], keep="last").sort_values("Date")


def _coingecko_payload_to_daily_frame(payload: dict, previous_close: float | None = None) -> pd.DataFrame:
    prices = payload.get("prices", [])
    volumes = payload.get("total_volumes", [])
    if not prices:
        return pd.DataFrame(columns=_BTC_DAILY_COLUMNS)

    close_by_date: dict[pd.Timestamp, float] = {}
    for unix_ms, value in prices:
        try:
            date = pd.to_datetime(int(unix_ms), unit="ms", utc=True).tz_convert(None).normalize()
            close_by_date[date] = float(value)
        except Exception:
            continue

    if not close_by_date:
        return pd.DataFrame(columns=_BTC_DAILY_COLUMNS)

    volume_by_date: dict[pd.Timestamp, float] = {}
    for unix_ms, value in volumes:
        try:
            date = pd.to_datetime(int(unix_ms), unit="ms", utc=True).tz_convert(None).normalize()
            volume_by_date[date] = float(value)
        except Exception:
            continue

    rows: list[tuple[pd.Timestamp, float, float, float, float, float, float]] = []
    prev_close = previous_close
    for date in sorted(close_by_date.keys()):
        close_px = float(close_by_date[date])
        if prev_close is None or pd.isna(prev_close):
            open_px = close_px
            change_pct = 0.0
        else:
            open_px = float(prev_close)
            change_pct = 0.0 if open_px == 0 else ((close_px / open_px) - 1.0) * 100.0

        high_px = float(max(open_px, close_px))
        low_px = float(min(open_px, close_px))
        volume = float(volume_by_date.get(date, float("nan")))
        rows.append((date, open_px, high_px, low_px, close_px, volume, round(change_pct, 2)))
        prev_close = close_px

    return pd.DataFrame(rows, columns=_BTC_DAILY_COLUMNS).drop_duplicates(subset=["Date"], keep="last").sort_values("Date")


def _fetch_coingecko_daily_frame(cfg: RuntimeConfig, previous_close: float | None = None) -> pd.DataFrame:
    try:
        response = requests.get(
            COINGECKO_MARKET_CHART_URL,
            params={"vs_currency": "usd", "days": "max"},
            timeout=cfg.request_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return pd.DataFrame(columns=_BTC_DAILY_COLUMNS)

    return _coingecko_payload_to_daily_frame(payload, previous_close=previous_close)


def _bootstrap_btc_daily_from_coingecko(cfg: RuntimeConfig) -> pd.DataFrame:
    frame = _fetch_coingecko_daily_frame(cfg)
    frame = frame[frame["Date"] <= _yesterday_utc()]
    if frame.empty:
        raise RuntimeError("Failed to bootstrap BTC daily from CoinGecko: produced empty frame")
    return frame


def refresh_btc_daily_from_binance(cfg: RuntimeConfig, symbol: str = "BTCUSDT") -> dict:
    csv_path = cfg.data_dir / "btc_daily.csv"
    if csv_path.exists():
        existing = _read_existing_btc_daily(csv_path)
        if existing.empty:
            raise ValueError(f"BTC daily file has no usable rows: {csv_path}")
    else:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        existing = _bootstrap_btc_daily_from_coingecko(cfg)
        existing.to_csv(csv_path, index=False, float_format="%.2f")
        return {
            "path": str(csv_path),
            "rows_before": 0,
            "rows_after": int(len(existing)),
            "rows_added": int(len(existing)),
            "last_date_before": None,
            "last_date_after": str(pd.Timestamp(existing["Date"].max()).date()),
        }

    last_date = pd.Timestamp(existing["Date"].max()).normalize()
    next_date = last_date + pd.Timedelta(days=1)
    next_start_ms = int(next_date.tz_localize("UTC").timestamp() * 1000)

    fetched_frames: List[pd.DataFrame] = []
    cursor_ms = next_start_ms
    interval_ms = 24 * 60 * 60 * 1000

    while True:
        batch = _fetch_binance_klines_page(
            symbol=symbol,
            interval="1d",
            start_time_ms=cursor_ms,
            timeout_seconds=cfg.request_timeout_seconds,
        )
        if not batch:
            break

        frame = _klines_to_frame(batch)
        if frame.empty:
            break
        fetched_frames.append(frame)

        last_open_time_ms = int(batch[-1][0])
        next_cursor_ms = last_open_time_ms + interval_ms
        if next_cursor_ms <= cursor_ms:
            break
        cursor_ms = next_cursor_ms
        if len(batch) < 1000:
            break

    if fetched_frames:
        fetched = pd.concat(fetched_frames, ignore_index=True)
        fetched = fetched.drop_duplicates(subset=["Date"], keep="last").sort_values("Date")
        fetch_mode = "binance"
    else:
        fetched = pd.DataFrame(columns=_BTC_DAILY_COLUMNS)
        fetch_mode = "none"

    yesterday_utc = _yesterday_utc()
    fetched = fetched[fetched["Date"] <= yesterday_utc].copy()
    needs_update = next_date <= yesterday_utc

    if fetched.empty and needs_update:
        previous_close = float(existing.iloc[-1]["Price"]) if not existing.empty else None
        fallback = _fetch_coingecko_daily_frame(cfg, previous_close=previous_close)
        fallback = fallback[(fallback["Date"] >= next_date) & (fallback["Date"] <= yesterday_utc)].copy()
        if not fallback.empty:
            fetched = fallback
            fetch_mode = "coingecko_fallback"

    if fetched.empty:
        merged = existing.copy()
    else:
        merged = pd.concat([existing, fetched], ignore_index=True)
    merged = merged.drop_duplicates(subset=["Date"], keep="last").sort_values("Date")
    merged = merged[_BTC_DAILY_COLUMNS]
    merged.to_csv(csv_path, index=False, float_format="%.2f")

    last_after = pd.Timestamp(merged["Date"].max()).normalize()
    today_utc = _yesterday_utc() + pd.Timedelta(days=1)
    staleness_days = int((today_utc - last_after).days)
    if staleness_days > 3:
        raise RuntimeError(
            f"BTC daily refresh is stale after update attempt ({staleness_days}d > 3d). "
            f"Last date in store: {last_after.date()}."
        )

    return {
        "path": str(csv_path),
        "rows_before": int(len(existing)),
        "rows_after": int(len(merged)),
        "rows_added": int(max(len(merged) - len(existing), 0)),
        "last_date_before": str(last_date.date()),
        "last_date_after": str(pd.Timestamp(merged["Date"].max()).date()),
        "fetch_mode": fetch_mode,
    }
