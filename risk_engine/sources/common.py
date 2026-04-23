from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
import requests


def safe_get_json(url: str, timeout_seconds: int, headers: Optional[dict] = None, params: Optional[dict] = None) -> Optional[dict]:
    try:
        response = requests.get(url, headers=headers, params=params, timeout=timeout_seconds)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def sanitize_series(series: pd.Series) -> pd.Series:
    parsed_index = pd.to_datetime(series.index, utc=True, errors="coerce").tz_convert(None)
    clean = pd.Series(series.values, index=parsed_index, name=series.name)
    clean = clean[~clean.index.isna()]
    clean = pd.to_numeric(clean, errors="coerce")
    clean = clean.dropna()
    clean = clean[~clean.index.duplicated(keep="last")]
    return clean.sort_index()


def series_staleness_days(series: pd.Series, as_of: Optional[pd.Timestamp] = None) -> Optional[int]:
    clean = sanitize_series(series)
    if clean.empty:
        return None

    now = as_of or pd.Timestamp.utcnow().tz_localize(None).normalize()
    last_date = clean.index.max().normalize()
    return int((now - last_date).days)


def load_optional_csv(path: Optional[Path], value_column: str, date_column: str = "Date") -> Optional[pd.Series]:
    if path is None or not path.exists():
        return None

    frame = pd.read_csv(path)
    if date_column not in frame.columns or value_column not in frame.columns:
        return None

    frame[date_column] = pd.to_datetime(frame[date_column], utc=False).dt.tz_localize(None)
    series = pd.Series(frame[value_column].values, index=frame[date_column], name=value_column)
    return sanitize_series(series)


def save_series_csv(path: Path, series: pd.Series, value_column: str) -> None:
    clean = sanitize_series(series)
    export = pd.DataFrame({"Date": clean.index, value_column: clean.values})
    export.to_csv(path, index=False)
