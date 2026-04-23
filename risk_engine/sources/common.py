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


def load_optional_csv(path: Optional[Path], value_column: str, date_column: str = "Date") -> Optional[pd.Series]:
    if path is None or not path.exists():
        return None

    frame = pd.read_csv(path)
    if date_column not in frame.columns or value_column not in frame.columns:
        return None

    frame[date_column] = pd.to_datetime(frame[date_column], utc=False).dt.tz_localize(None)
    series = pd.Series(frame[value_column].astype(float).values, index=frame[date_column], name=value_column)
    return series.sort_index()


def save_series_csv(path: Path, series: pd.Series, value_column: str) -> None:
    export = pd.DataFrame({"Date": series.index, value_column: series.values})
    export.to_csv(path, index=False)
