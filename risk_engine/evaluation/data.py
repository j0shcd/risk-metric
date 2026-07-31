from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable, List

import pandas as pd

from .schemas import DataFingerprint


def dataframe_fingerprint(name: str, frame: pd.DataFrame) -> DataFingerprint:
    ordered = frame.sort_index().copy()
    csv_payload = ordered.to_csv(index=True, date_format="%Y-%m-%dT%H:%M:%S")
    digest = hashlib.sha256(csv_payload.encode("utf-8")).hexdigest()

    start_date = None
    end_date = None
    if not ordered.empty:
        start_date = pd.Timestamp(ordered.index.min()).date().isoformat()
        end_date = pd.Timestamp(ordered.index.max()).date().isoformat()

    return DataFingerprint(
        name=name,
        rows=int(ordered.shape[0]),
        columns=int(ordered.shape[1]),
        start_date=start_date,
        end_date=end_date,
        sha256=digest,
    )


def file_fingerprint(path: Path, *, name: str | None = None) -> DataFingerprint:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return DataFingerprint(
        name=name or str(path),
        rows=0,
        columns=0,
        start_date=None,
        end_date=None,
        sha256=digest,
    )


def assert_monotonic_datetime_index(frame: pd.DataFrame) -> List[str]:
    warnings: List[str] = []
    if not isinstance(frame.index, pd.DatetimeIndex):
        warnings.append("index_not_datetime")
        return warnings
    if frame.index.has_duplicates:
        warnings.append("duplicate_dates")
    if not frame.index.is_monotonic_increasing:
        warnings.append("index_not_monotonic")
    return warnings
