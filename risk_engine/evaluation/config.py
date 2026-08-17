from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .schemas import AvailabilityRule, EvaluationConfig, MetricDefinition, RegisteredHypothesis, json_safe


# DCA Risk promotion is governed by the compact evidence suite rather than the
# generic short-horizon label grid. The grid remains available for exploration.
REGISTERED_DCA_HYPOTHESES: List[RegisteredHypothesis] = []


DEFAULT_METRICS: List[MetricDefinition] = [
    MetricDefinition("top_reversal_risk", "ordinal", "future drawdown/top labels"),
    MetricDefinition("bottom_reversal_risk", "ordinal", "future rally/bottom labels"),
    MetricDefinition("dca_risk", "policy_signal", "monthly DCA timing quality"),
    MetricDefinition(
        "dca_top_reversal_component",
        "policy_signal_component",
        "exploratory DCA timing component contribution",
        confirmatory=False,
    ),
    MetricDefinition(
        "dca_bottom_reversal_component",
        "policy_signal_component",
        "exploratory DCA timing component contribution",
        confirmatory=False,
    ),
    MetricDefinition(
        "dca_cycle_extension_component",
        "policy_signal_component",
        "exploratory DCA timing component contribution",
        confirmatory=False,
    ),
    MetricDefinition(
        "dca_cycle_regime_component",
        "policy_signal_component",
        "exploratory DCA timing component contribution",
        confirmatory=False,
    ),
    MetricDefinition("btc_risk_signal", "index", "broad future downside/upside asymmetry"),
    MetricDefinition("total_market_risk_signal", "index", "broad market-cycle context"),
    MetricDefinition("trend_composite_score", "index", "trend/cycle extension"),
    MetricDefinition("attention_score", "index", "future realized volatility"),
    MetricDefinition("headline_attention", "index", "future volatility and crowdedness"),
    MetricDefinition("cycle_extension_score", "ordinal", "future drawdown risk"),
    MetricDefinition("cycle_frenzy_score", "ordinal", "top-risk outcomes"),
    MetricDefinition("cycle_accumulation_score", "ordinal", "bottom-opportunity outcomes"),
    MetricDefinition("cycle_p_frenzy", "probability_like", "fitted frenzy-regime probability"),
    MetricDefinition("cycle_p_accumulation", "probability_like", "fitted accumulation-regime probability"),
]

SMOKE_REQUIRED_COLUMNS = [
    "btc_price",
    "top_reversal_risk",
    "bottom_reversal_risk",
    "dca_risk",
]

DEFAULT_REQUIRED_COLUMNS = ["btc_price", *[metric.name for metric in DEFAULT_METRICS]]

PROFILE_REQUIRED_COLUMNS: Dict[str, List[str]] = {
    "smoke": SMOKE_REQUIRED_COLUMNS,
    "standard": DEFAULT_REQUIRED_COLUMNS,
    "expensive": DEFAULT_REQUIRED_COLUMNS,
    "dashboard": DEFAULT_REQUIRED_COLUMNS,
}

DEFAULT_SOURCE_LATENCY_DAYS: Dict[str, int] = {
    "btc_price": 1,
    "total_market_cap": 1,
    "fear_greed_index": 1,
    "onchain::*": 3,
    "social::*": 7,
    "cycle::*": 1,
}

DEFAULT_AVAILABILITY_RULES: List[AvailabilityRule] = [
    AvailabilityRule(
        name="btc_price",
        entity_type="source",
        latency_days=1,
        availability_assumption="daily close available next day",
        availability_confidence="estimated",
        source_trust_tier="high",
        data_processing_state="cleaned",
    ),
    AvailabilityRule(
        name="total_market_cap",
        entity_type="source",
        latency_days=1,
        availability_assumption="market-cap source available next day",
        availability_confidence="estimated",
        source_trust_tier="medium",
        data_processing_state="cleaned",
    ),
    AvailabilityRule(
        name="fear_greed_index",
        entity_type="source",
        latency_days=1,
        availability_assumption="daily index available next day",
        availability_confidence="estimated",
        source_trust_tier="medium",
        data_processing_state="cleaned",
    ),
    AvailabilityRule(
        name="onchain::*",
        entity_type="source",
        latency_days=3,
        availability_assumption="onchain provider lag estimated from typical daily availability",
        availability_confidence="estimated",
        source_trust_tier="medium",
        data_processing_state="cleaned",
    ),
    AvailabilityRule(
        name="social::*",
        entity_type="source",
        latency_days=7,
        availability_assumption="social/attention source lag estimated conservatively",
        availability_confidence="estimated",
        source_trust_tier="low",
        data_processing_state="cleaned",
    ),
    AvailabilityRule(
        name="cycle::*",
        entity_type="source",
        latency_days=1,
        availability_assumption="derived cycle context available after underlying daily close",
        availability_confidence="estimated",
        source_trust_tier="medium",
        data_processing_state="derived",
    ),
]


def _new_run_id(profile: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{profile}"


def build_evaluation_config(
    *,
    output_dir: Path,
    profile: str = "smoke",
    run_id: str | None = None,
    seed: int = 1729,
    cycle_dynamic_dca_buy_threshold: float = 0.75,
    cycle_dynamic_dca_sell_threshold: float = 0.75,
    cycle_dynamic_dca_base_contribution: float = 1.0,
    cycle_dynamic_dca_max_buy_multiplier: float = 3.0,
    cycle_dynamic_dca_max_sell_fraction: float = 0.35,
    cycle_dynamic_dca_cash_buffer_ratio: float = 0.10,
    cycle_dynamic_dca_fee_rate: float = 0.001,
    cycle_dynamic_dca_slippage_rate: float = 0.001,
) -> EvaluationConfig:
    normalized_profile = profile.strip().lower()
    if normalized_profile not in PROFILE_REQUIRED_COLUMNS:
        known = ", ".join(sorted(PROFILE_REQUIRED_COLUMNS))
        raise ValueError(f"unknown evaluation profile {profile!r}; expected one of {known}")
    return EvaluationConfig(
        profile=normalized_profile,
        output_dir=output_dir,
        run_id=run_id or _new_run_id(normalized_profile),
        seed=int(seed),
        metrics=list(DEFAULT_METRICS),
        registered_hypotheses=list(REGISTERED_DCA_HYPOTHESES),
        required_columns=list(PROFILE_REQUIRED_COLUMNS[normalized_profile]),
        smoke_mode=normalized_profile == "smoke",
        cycle_dynamic_dca_buy_threshold=float(cycle_dynamic_dca_buy_threshold),
        cycle_dynamic_dca_sell_threshold=float(cycle_dynamic_dca_sell_threshold),
        cycle_dynamic_dca_base_contribution=float(cycle_dynamic_dca_base_contribution),
        cycle_dynamic_dca_max_buy_multiplier=float(cycle_dynamic_dca_max_buy_multiplier),
        cycle_dynamic_dca_max_sell_fraction=float(cycle_dynamic_dca_max_sell_fraction),
        cycle_dynamic_dca_cash_buffer_ratio=float(cycle_dynamic_dca_cash_buffer_ratio),
        cycle_dynamic_dca_fee_rate=float(cycle_dynamic_dca_fee_rate),
        cycle_dynamic_dca_slippage_rate=float(cycle_dynamic_dca_slippage_rate),
        source_latency_days=dict(DEFAULT_SOURCE_LATENCY_DAYS),
        availability_rules=list(DEFAULT_AVAILABILITY_RULES),
    )


def config_to_dict(config: EvaluationConfig) -> Dict[str, Any]:
    return json_safe(asdict(config))


def config_hash(config: EvaluationConfig) -> str:
    stable = replace(config, run_id="<run_id>")
    payload = json.dumps(config_to_dict(stable), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def config_to_json(config: EvaluationConfig) -> str:
    return json.dumps(config_to_dict(config), sort_keys=True, indent=2) + "\n"
