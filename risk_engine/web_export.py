from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

import numpy as np
import pandas as pd

from .types import RiskOutput
from .validation import ValidationResult


WEB_V1_VERSION = "v1"
WEB_V1_SCHEMA_VERSION = "1.0.0"

WEB_V1_ARTIFACTS = [
    "manifest.json",
    "latest_snapshot.json",
    "history_core.json",
    "category_breakdowns_btc.json",
    "category_breakdowns_total_market.json",
    "metric_breakdowns_btc.json",
    "metric_breakdowns_total_market.json",
    "diagnostics.json",
]

CORE_HISTORY_COLUMNS = [
    "btc_risk_heat",
    "btc_risk_attention",
    "btc_risk_confidence",
    "btc_risk_coverage",
    "total_market_risk_heat",
    "total_market_risk_attention",
    "total_market_risk_confidence",
    "total_market_risk_coverage",
    "headline_attention",
    "headline_heat",
    "confidence_score",
    "cycle_heat_score",
    "cycle_cold_score",
    "cycle_p_frenzy",
    "cycle_p_accumulation",
    "cycle_confidence",
    "cycle_position",
    "btc_price",
    "total_market_cap",
]


@dataclass(frozen=True)
class WebExportResult:
    root: Path
    manifest: Dict[str, Any]
    files: List[Path]


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _to_iso_timestamp(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, str):
        return value

    if isinstance(value, (datetime, pd.Timestamp)):
        timestamp = pd.Timestamp(value)
        if pd.isna(timestamp):
            return None
        if timestamp.tzinfo is not None:
            timestamp = timestamp.tz_convert("UTC")
        return timestamp.isoformat().replace("+00:00", "Z")

    return str(value)


def _coerce_json_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return _to_iso_timestamp(value)
    if isinstance(value, (np.floating, float)):
        if np.isnan(value):
            return None
        return float(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if pd.isna(value):
        return None
    return value


def _index_to_iso_dates(index: Iterable[Any]) -> List[str]:
    values: List[str] = []
    for item in index:
        ts = pd.Timestamp(item)
        if pd.isna(ts):
            values.append("")
            continue
        values.append(ts.date().isoformat())
    return values


def _columnar_payload(frame: pd.DataFrame, *, index_name: str = "date") -> Dict[str, Any]:
    ordered = frame.sort_index()
    return {
        "index_name": index_name,
        "index": _index_to_iso_dates(ordered.index),
        "columns": {
            str(column): [_coerce_json_scalar(value) for value in ordered[column].tolist()] for column in ordered.columns
        },
    }


def _records_payload(frame: pd.DataFrame) -> List[Dict[str, Any]]:
    if frame.empty:
        return []

    normalized = frame.copy()
    for column in normalized.columns:
        if pd.api.types.is_datetime64_any_dtype(normalized[column]):
            normalized[column] = normalized[column].map(_to_iso_timestamp)

    records: List[Dict[str, Any]] = []
    for row in normalized.to_dict(orient="records"):
        records.append({str(key): _coerce_json_scalar(value) for key, value in row.items()})
    return records


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _latest_snapshot(series: pd.DataFrame) -> Dict[str, Any]:
    latest_row = series.sort_index().tail(1)
    if latest_row.empty:
        return {
            "date": None,
            "btc_risk": {
                "heat": None,
                "attention": None,
                "confidence": None,
                "coverage": None,
            },
            "total_market_risk": {
                "heat": None,
                "attention": None,
                "confidence": None,
                "coverage": None,
            },
            "headline_attention": None,
            "headline_heat": None,
            "confidence_score": None,
            "cycle_model": {
                "heat_score": None,
                "cold_score": None,
                "p_frenzy": None,
                "p_accumulation": None,
                "confidence": None,
                "position": None,
                "signal_regime": None,
            },
        }

    date = latest_row.index[-1]
    row = latest_row.iloc[-1]
    return {
        "date": pd.Timestamp(date).date().isoformat(),
        "btc_risk": {
            "heat": _coerce_json_scalar(row.get("btc_risk_heat")),
            "attention": _coerce_json_scalar(row.get("btc_risk_attention")),
            "confidence": _coerce_json_scalar(row.get("btc_risk_confidence")),
            "coverage": _coerce_json_scalar(row.get("btc_risk_coverage")),
        },
        "total_market_risk": {
            "heat": _coerce_json_scalar(row.get("total_market_risk_heat")),
            "attention": _coerce_json_scalar(row.get("total_market_risk_attention")),
            "confidence": _coerce_json_scalar(row.get("total_market_risk_confidence")),
            "coverage": _coerce_json_scalar(row.get("total_market_risk_coverage")),
        },
        "headline_attention": _coerce_json_scalar(row.get("headline_attention")),
        "headline_heat": _coerce_json_scalar(row.get("headline_heat")),
        "confidence_score": _coerce_json_scalar(row.get("confidence_score")),
        "cycle_model": {
            "heat_score": _coerce_json_scalar(row.get("cycle_heat_score")),
            "cold_score": _coerce_json_scalar(row.get("cycle_cold_score")),
            "p_frenzy": _coerce_json_scalar(row.get("cycle_p_frenzy")),
            "p_accumulation": _coerce_json_scalar(row.get("cycle_p_accumulation")),
            "confidence": _coerce_json_scalar(row.get("cycle_confidence")),
            "position": _coerce_json_scalar(row.get("cycle_position")),
            "signal_regime": _coerce_json_scalar(row.get("cycle_signal_regime")),
        },
    }


def export_web_v1(
    result: RiskOutput,
    validation: ValidationResult,
    *,
    target_root: Path,
    sanity_report: pd.DataFrame,
    generated_at: str | None = None,
) -> WebExportResult:
    root = target_root / WEB_V1_VERSION
    generated_at_value = generated_at or _iso_utc_now()
    root.mkdir(parents=True, exist_ok=True)

    for existing in root.iterdir():
        if existing.is_dir():
            shutil.rmtree(existing)
        else:
            existing.unlink()

    series = result.series.copy().sort_index()
    history_frame = pd.DataFrame(index=series.index)
    for column in CORE_HISTORY_COLUMNS:
        history_frame[column] = series[column] if column in series.columns else np.nan

    source_modes = [
        {"source": source, "mode": mode}
        for source, mode in sorted(result.source_modes.items(), key=lambda item: item[0])
    ]

    diagnostics_payload = {
        "validation": {
            "passed": bool(validation.passed),
            "errors": [str(item) for item in validation.errors],
            "warnings": [str(item) for item in validation.warnings],
        },
        "source_modes": source_modes,
        "source_health": _records_payload(result.source_health.sort_values("source") if not result.source_health.empty else result.source_health),
        "metric_health": _records_payload(
            result.metric_health.sort_values(["category", "target", "metric", "bundle"], na_position="last")
            if not result.metric_health.empty
            else result.metric_health
        ),
        "sanity_report": _records_payload(sanity_report),
    }

    latest_snapshot_payload = _latest_snapshot(series)

    files: List[Path] = []

    latest_snapshot_path = root / "latest_snapshot.json"
    _write_json(
        latest_snapshot_path,
        {
            "generated_at": generated_at_value,
            "schema_version": WEB_V1_SCHEMA_VERSION,
            "version": WEB_V1_VERSION,
            **latest_snapshot_payload,
        },
    )
    files.append(latest_snapshot_path)

    history_core_path = root / "history_core.json"
    _write_json(
        history_core_path,
        {
            "generated_at": generated_at_value,
            "schema_version": WEB_V1_SCHEMA_VERSION,
            "version": WEB_V1_VERSION,
            **_columnar_payload(history_frame),
        },
    )
    files.append(history_core_path)

    category_btc_path = root / "category_breakdowns_btc.json"
    _write_json(
        category_btc_path,
        {
            "generated_at": generated_at_value,
            "schema_version": WEB_V1_SCHEMA_VERSION,
            "target": "btc",
            "version": WEB_V1_VERSION,
            **_columnar_payload(result.category_breakdowns.get("btc", pd.DataFrame())),
        },
    )
    files.append(category_btc_path)

    category_total_path = root / "category_breakdowns_total_market.json"
    _write_json(
        category_total_path,
        {
            "generated_at": generated_at_value,
            "schema_version": WEB_V1_SCHEMA_VERSION,
            "target": "total_market",
            "version": WEB_V1_VERSION,
            **_columnar_payload(result.category_breakdowns.get("total_market", pd.DataFrame())),
        },
    )
    files.append(category_total_path)

    metric_btc_path = root / "metric_breakdowns_btc.json"
    _write_json(
        metric_btc_path,
        {
            "generated_at": generated_at_value,
            "schema_version": WEB_V1_SCHEMA_VERSION,
            "target": "btc",
            "version": WEB_V1_VERSION,
            **_columnar_payload(result.metric_breakdowns.get("btc", pd.DataFrame())),
        },
    )
    files.append(metric_btc_path)

    metric_total_path = root / "metric_breakdowns_total_market.json"
    _write_json(
        metric_total_path,
        {
            "generated_at": generated_at_value,
            "schema_version": WEB_V1_SCHEMA_VERSION,
            "target": "total_market",
            "version": WEB_V1_VERSION,
            **_columnar_payload(result.metric_breakdowns.get("total_market", pd.DataFrame())),
        },
    )
    files.append(metric_total_path)

    diagnostics_path = root / "diagnostics.json"
    _write_json(
        diagnostics_path,
        {
            "generated_at": generated_at_value,
            "schema_version": WEB_V1_SCHEMA_VERSION,
            "version": WEB_V1_VERSION,
            **diagnostics_payload,
        },
    )
    files.append(diagnostics_path)

    manifest = {
        "version": WEB_V1_VERSION,
        "schema_version": WEB_V1_SCHEMA_VERSION,
        "generated_at": generated_at_value,
        "artifacts": sorted(WEB_V1_ARTIFACTS),
    }

    manifest_path = root / "manifest.json"
    _write_json(manifest_path, manifest)
    files.append(manifest_path)

    return WebExportResult(root=root, manifest=manifest, files=files)
