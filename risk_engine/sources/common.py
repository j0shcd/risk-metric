from __future__ import annotations

import json
import math
import time
from urllib.parse import urlsplit
from pathlib import Path
from typing import Optional

import pandas as pd
import requests


MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_REQUEST_SECONDS = 60
READ_TIMEOUT_SECONDS = 10


def _reject_redirect(response, *args, **kwargs):
    # Requests prepares response.next even when redirects are disabled, consuming
    # a redirect body before returning it. Reject in the response hook first.
    if 300 <= response.status_code < 400:
        response.close()
        raise ValueError("provider redirect rejected")
    return response


def _get_body(url: str, timeout_seconds: int, headers=None, params=None):
    """One production HTTP boundary: HTTPS, no redirects, bounded decoded body.

    Elapsed checks run at streaming checkpoints; Requests socket timeouts are
    inactivity limits, not a hard wall deadline (notably during DNS). Hosted job
    deadlines provide the independent outer bound. Never include URLs/keys in errors.
    """
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("provider URL must use HTTPS without userinfo")
    timeout = float(timeout_seconds)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("invalid request timeout")
    started = time.monotonic()
    with requests.get(url, headers=headers, params=params,
                      timeout=min(timeout, READ_TIMEOUT_SECONDS),
                      allow_redirects=False, stream=True,
                      hooks={"response": _reject_redirect}) as response:
        if not 200 <= response.status_code < 300:
            raise ValueError("provider returned a non-success response")
        length = response.headers.get("Content-Length")
        if length is not None and not 0 <= int(length) <= MAX_RESPONSE_BYTES:
            raise ValueError("provider response exceeds byte budget")
        body = bytearray()
        for chunk in response.iter_content(chunk_size=16 * 1024):
            if time.monotonic() - started >= MAX_REQUEST_SECONDS:
                raise TimeoutError("provider elapsed budget exceeded")
            if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                raise ValueError("provider decoded response exceeds byte budget")
            body.extend(chunk)
        if time.monotonic() - started >= MAX_REQUEST_SECONDS:
            raise TimeoutError("provider elapsed budget exceeded")
        return bytes(body), response.encoding or "utf-8"


def request_json(url: str, timeout_seconds: int, headers=None, params=None):
    body, _ = _get_body(url, timeout_seconds, headers, params)
    return json.loads(body)


def safe_get_json(url: str, timeout_seconds: int, headers: Optional[dict] = None, params: Optional[dict] = None):
    try:
        return request_json(url, timeout_seconds, headers, params)
    except Exception:
        return None


def safe_get_text(url: str, timeout_seconds: int, headers: Optional[dict] = None,
                  params: Optional[dict] = None) -> Optional[str]:
    try:
        body, encoding = _get_body(url, timeout_seconds, headers, params)
        return body.decode(encoding, errors="replace")
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

    now = as_of or pd.Timestamp.now("UTC").tz_localize(None).normalize()
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
