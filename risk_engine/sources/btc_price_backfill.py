from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd
import requests

from ..config import RuntimeConfig


BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
_BTC_DAILY_COLUMNS = ["Date", "Open", "High", "Low", "Price", "Vol.", "Change %"]


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


def refresh_btc_daily_from_binance(cfg: RuntimeConfig, symbol: str = "BTCUSDT") -> dict:
    csv_path = cfg.data_dir / "btc_daily.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing BTC data file: {csv_path}")

    existing = _read_existing_btc_daily(csv_path)
    if existing.empty:
        raise ValueError(f"BTC daily file has no usable rows: {csv_path}")

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
    else:
        fetched = pd.DataFrame(columns=_BTC_DAILY_COLUMNS)

    yesterday_utc = pd.Timestamp.utcnow().tz_localize(None).normalize() - pd.Timedelta(days=1)
    fetched = fetched[fetched["Date"] <= yesterday_utc].copy()

    if fetched.empty:
        merged = existing.copy()
    else:
        merged = pd.concat([existing, fetched], ignore_index=True)
    merged = merged.drop_duplicates(subset=["Date"], keep="last").sort_values("Date")
    merged = merged[_BTC_DAILY_COLUMNS]
    merged.to_csv(csv_path, index=False, float_format="%.2f")

    return {
        "path": str(csv_path),
        "rows_before": int(len(existing)),
        "rows_after": int(len(merged)),
        "rows_added": int(max(len(merged) - len(existing), 0)),
        "last_date_before": str(last_date.date()),
        "last_date_after": str(pd.Timestamp(merged["Date"].max()).date()),
    }
