from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import pandas as pd


@dataclass(frozen=True)
class FeatureBundle:
    name: str
    category: str
    target: str
    frame: pd.DataFrame
    experimental: bool = False


@dataclass(frozen=True)
class RiskOutput:
    series: pd.DataFrame
    feature_frames: Dict[str, pd.DataFrame]
    metric_health: pd.DataFrame = field(default_factory=pd.DataFrame)
    source_health: pd.DataFrame = field(default_factory=pd.DataFrame)
    source_modes: Dict[str, str] = field(default_factory=dict)
    category_breakdowns: Dict[str, pd.DataFrame] = field(default_factory=dict)
    metric_breakdowns: Dict[str, pd.DataFrame] = field(default_factory=dict)
    cycle_feature_snapshots: pd.DataFrame = field(default_factory=pd.DataFrame)
    cycle_regime_scores: pd.DataFrame = field(default_factory=pd.DataFrame)
    cycle_signal_decisions: pd.DataFrame = field(default_factory=pd.DataFrame)
    cycle_backtest_report: pd.DataFrame = field(default_factory=pd.DataFrame)
    financial_benchmark_summary: pd.DataFrame = field(default_factory=pd.DataFrame)
    financial_benchmark_curves: pd.DataFrame = field(default_factory=pd.DataFrame)
    cycle_metric_audit: pd.DataFrame = field(default_factory=pd.DataFrame)
    cycle_migration_plan: str = ""
    benchmark_summary: pd.DataFrame = field(default_factory=pd.DataFrame)
    benchmark_by_label: pd.DataFrame = field(default_factory=pd.DataFrame)
    benchmark_by_signal: pd.DataFrame = field(default_factory=pd.DataFrame)
    benchmark_window_stats: pd.DataFrame = field(default_factory=pd.DataFrame)
    benchmark_config: Dict[str, object] = field(default_factory=dict)
    benchmark_warnings: List[str] = field(default_factory=list)
    benchmark_baseline: Dict[str, object] = field(default_factory=dict)
    benchmark_deltas: Dict[str, object] = field(default_factory=dict)
    benchmark_regression_warnings: List[str] = field(default_factory=list)
    operational_alert_policy: Dict[str, object] = field(default_factory=dict)
    calibration_metadata: Dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class FeatureSnapshot:
    date: pd.Timestamp
    valuation_features: Dict[str, float]
    speculation_features: Dict[str, float]
    attention_features: Dict[str, float]
    macro_features: Dict[str, float]


@dataclass(frozen=True)
class RegimeScores:
    date: pd.Timestamp
    frenzy_score: float
    accumulation_score: float
    p_frenzy: float
    p_accumulation: float
    confidence: float


@dataclass(frozen=True)
class SignalDecision:
    date: pd.Timestamp
    regime: str
    trigger_features: List[str]
    cooldown_state: int


@dataclass(frozen=True)
class BacktestReport:
    window: str
    trades: int
    cycle_capture: float
    max_drawdown: float
    turnover: float
    benchmark_comparison: Dict[str, float]
