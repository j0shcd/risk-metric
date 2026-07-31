from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return json_safe(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (pd.Timestamp, datetime)):
        timestamp = pd.Timestamp(value)
        if pd.isna(timestamp):
            return None
        if timestamp.tzinfo is not None:
            timestamp = timestamp.tz_convert("UTC")
        return timestamp.isoformat().replace("+00:00", "Z")
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        if not np.isfinite(value):
            return None
        return float(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


@dataclass(frozen=True)
class MetricDefinition:
    name: str
    semantic_type: str
    primary_outcome: str
    confirmatory: bool = True


@dataclass(frozen=True)
class RegisteredHypothesis:
    hypothesis_id: str
    signal: str
    label_id: str
    expected_direction: str
    horizon_months: int
    primary_statistic: str
    endpoint: str


@dataclass(frozen=True)
class ClaimGateConfig:
    min_events_short_medium: int = 8
    min_events_long: int = 5
    min_effective_obs_short_medium: int = 30
    min_effective_obs_long: int = 12
    fdr_alpha: float = 0.10
    max_event_year_share: float = 0.67
    min_event_years: int = 2
    max_cost_drag: float = 0.02
    max_turnover_per_year: float = 6.0


@dataclass(frozen=True)
class AvailabilityRule:
    name: str
    entity_type: str
    latency_days: int
    availability_assumption: str
    availability_confidence: str
    source_trust_tier: str
    data_processing_state: str


@dataclass(frozen=True)
class EvaluationConfig:
    profile: str
    output_dir: Path
    run_id: str
    seed: int = 1729
    metric_definition_frozen_at: str = "2026-06-21"
    plan_path: str = "docs/metric_evaluation_plan.md"
    metrics: List[MetricDefinition] = field(default_factory=list)
    registered_hypotheses: List[RegisteredHypothesis] = field(default_factory=list)
    claim_gates: ClaimGateConfig = field(default_factory=ClaimGateConfig)
    required_columns: List[str] = field(default_factory=list)
    smoke_mode: bool = False
    cycle_dynamic_dca_buy_threshold: float = 0.75
    cycle_dynamic_dca_sell_threshold: float = 0.75
    source_latency_days: Dict[str, int] = field(default_factory=dict)
    availability_rules: List[AvailabilityRule] = field(default_factory=list)


@dataclass(frozen=True)
class DataFingerprint:
    name: str
    rows: int
    columns: int
    start_date: Optional[str]
    end_date: Optional[str]
    sha256: str


@dataclass(frozen=True)
class EvaluationWarning:
    code: str
    severity: str
    message: str
    test_id: Optional[str] = None
    blocks_dashboard: bool = False


@dataclass(frozen=True)
class EvaluationTestResult:
    test_id: str
    family: str
    status: str
    severity: str
    summary: str
    result_type: str = "diagnostic"
    claim_scope: str = "none"
    metrics: Dict[str, Any] = field(default_factory=dict)
    warnings: List[EvaluationWarning] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class EvaluationManifest:
    run_id: str
    profile: str
    generated_at: str
    plan_path: str
    config_hash: str
    seed: int
    status: str
    git_commit: Optional[str]
    data_fingerprints: List[DataFingerprint]
    tests: List[EvaluationTestResult]
    warnings: List[EvaluationWarning]
    artifacts: List[str]
