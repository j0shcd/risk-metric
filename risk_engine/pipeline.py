from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd

from .config import RuntimeConfig, load_runtime_config
from .diagnostics import build_metric_health, build_source_health
from .features import build_market_features, build_onchain_features, build_social_sentiment_features
from .normalization import build_feature_frame
from .scoring import MetricSpec, score_target
from .sources import (
    load_btc_price,
    load_fear_greed_index,
    load_onchain_metrics,
    load_social_metrics,
    load_total_market_cap,
)
from .types import FeatureBundle, RiskOutput


def _metric_specs(cfg: RuntimeConfig) -> List[MetricSpec]:
    specs = [
        MetricSpec("btc_trend_extension_50d_350d", "price_structure", "btc", base_reliability=0.95, max_carry_days=7),
        MetricSpec("btc_running_roi_1y", "price_structure", "btc", base_reliability=0.95, max_carry_days=7),
        MetricSpec("btc_log_reg_deviation", "price_structure", "btc", base_reliability=0.95, max_carry_days=7),
        MetricSpec("total_trend_extension_50d_350d", "price_structure", "total_market", base_reliability=0.90, max_carry_days=7),
        MetricSpec("total_running_roi_1y", "price_structure", "total_market", base_reliability=0.90, max_carry_days=7),
        MetricSpec("total_log_reg_deviation", "price_structure", "total_market", base_reliability=0.90, max_carry_days=7),
        # Explicit fallback proxies when total market-cap history is unavailable.
        MetricSpec("btc_trend_extension_50d_350d", "price_structure", "total_market", base_reliability=0.35, max_carry_days=7),
        MetricSpec("btc_running_roi_1y", "price_structure", "total_market", base_reliability=0.35, max_carry_days=7),
        MetricSpec("btc_log_reg_deviation", "price_structure", "total_market", base_reliability=0.35, max_carry_days=7),
        MetricSpec("total_trend_extension_50d_350d", "total_market_context", "btc", base_reliability=0.85, max_carry_days=7),
        MetricSpec("total_log_reg_deviation", "total_market_context", "btc", base_reliability=0.85, max_carry_days=7),
        MetricSpec("btc_dominance_proxy", "total_market_context", "both", base_reliability=0.60, max_carry_days=14),
        MetricSpec("mvrv_z_score", "onchain", "both", base_reliability=0.85, max_carry_days=5),
        MetricSpec("puell_multiple", "onchain", "both", base_reliability=0.85, max_carry_days=5),
        MetricSpec("supply_in_profit", "onchain", "both", base_reliability=0.80, max_carry_days=5),
        MetricSpec("supply_in_loss", "onchain", "both", base_reliability=0.80, max_carry_days=5, direction=-1.0),
        MetricSpec("youtube_interest", "social", "both", base_reliability=0.60, max_carry_days=14),
        MetricSpec("google_trends_interest", "social", "both", base_reliability=0.50, max_carry_days=21),
        MetricSpec(
            "coinbase_app_rank_proxy",
            "social",
            "both",
            base_reliability=0.35,
            max_carry_days=14,
            experimental=True,
        ),
        MetricSpec("fear_greed_index", "fear_greed", "both", base_reliability=0.60, max_carry_days=7),
    ]

    if not cfg.enable_coinbase_app_rank:
        specs = [spec for spec in specs if spec.name != "coinbase_app_rank_proxy"]

    return specs


def _build_feature_bundles(raw_features: pd.DataFrame, metric_specs: List[MetricSpec]) -> List[FeatureBundle]:
    bundles: List[FeatureBundle] = []
    for spec in metric_specs:
        if spec.name not in raw_features.columns:
            continue

        frame = build_feature_frame(
            raw_series=raw_features[spec.name],
            base_reliability=spec.base_reliability,
            max_carry_days=spec.max_carry_days,
            direction=spec.direction,
        )
        bundle_name = f"{spec.name}__{spec.target}__{spec.category}"
        bundles.append(
            FeatureBundle(
                name=bundle_name,
                category=spec.category,
                target=spec.target,
                frame=frame,
                experimental=spec.experimental,
            )
        )

    return bundles


def run_pipeline(cfg: RuntimeConfig | None = None) -> RiskOutput:
    runtime = cfg or load_runtime_config()
    metric_specs = _metric_specs(runtime)

    btc_price = load_btc_price(runtime)
    index = btc_price.index

    total_market_cap = load_total_market_cap(runtime, index=index)
    onchain_frame = load_onchain_metrics(runtime, index=index)
    fear_greed = load_fear_greed_index(runtime, index=index)
    social_frame = load_social_metrics(runtime, index=index)

    market_features = build_market_features(btc_price=btc_price, total_market_cap=total_market_cap)
    onchain_features = build_onchain_features(onchain_frame)
    social_features = build_social_sentiment_features(fear_greed=fear_greed, social_frame=social_frame)

    raw_features = pd.concat([market_features, onchain_features, social_features], axis=1)

    bundles = _build_feature_bundles(raw_features=raw_features, metric_specs=metric_specs)

    btc_score = score_target(
        index=index,
        feature_bundles=bundles,
        category_weights=runtime.category_weights,
        target="btc",
    )
    total_score = score_target(
        index=index,
        feature_bundles=bundles,
        category_weights=runtime.category_weights,
        target="total_market",
    )

    output = pd.DataFrame(index=index)
    output["btc_risk_heat"] = btc_score.heat
    output["btc_risk_attention"] = btc_score.attention
    output["btc_risk_confidence"] = btc_score.confidence
    output["btc_risk_coverage"] = btc_score.coverage

    output["total_market_risk_heat"] = total_score.heat
    output["total_market_risk_attention"] = total_score.attention
    output["total_market_risk_confidence"] = total_score.confidence
    output["total_market_risk_coverage"] = total_score.coverage

    output["headline_attention"] = (
        0.7 * output["btc_risk_attention"] + 0.3 * output["total_market_risk_attention"]
    ).clip(0.0, 1.0)

    output["headline_direction"] = (
        0.7 * output["btc_risk_heat"] + 0.3 * output["total_market_risk_heat"]
    ).clip(-1.0, 1.0)

    output["confidence_score"] = (
        0.7 * output["btc_risk_confidence"] + 0.3 * output["total_market_risk_confidence"]
    ).clip(0.0, 1.0)

    output["btc_price"] = btc_price
    output["total_market_cap"] = total_market_cap

    as_of = pd.Timestamp.utcnow().tz_localize(None).normalize()

    source_map = {
        "btc_price": btc_price,
        "total_market_cap": total_market_cap,
        "fear_greed_index": fear_greed,
    }
    for column in onchain_frame.columns:
        source_map[f"onchain::{column}"] = onchain_frame[column]
    for column in social_frame.columns:
        source_map[f"social::{column}"] = social_frame[column]

    metric_health = build_metric_health(
        metric_specs=metric_specs,
        feature_bundles=bundles,
        as_of=as_of,
        lookback_days=30,
    )
    source_health = build_source_health(source_map=source_map, as_of=as_of, lookback_days=30)

    return RiskOutput(
        series=output,
        feature_frames={bundle.name: bundle.frame for bundle in bundles},
        metric_health=metric_health,
        source_health=source_health,
        category_breakdowns={
            "btc": btc_score.category_breakdown,
            "total_market": total_score.category_breakdown,
        },
    )


def write_outputs(result: RiskOutput, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    latest_path = output_dir / "latest_scores.csv"
    full_path = output_dir / "risk_scores_full.csv"

    result.series.to_csv(full_path)

    latest = result.series.tail(1)
    latest.to_csv(latest_path)

    features_path = output_dir / "feature_frames"
    features_path.mkdir(parents=True, exist_ok=True)
    for existing in features_path.glob("*.csv"):
        existing.unlink()

    for name, frame in result.feature_frames.items():
        frame.to_csv(features_path / f"{name}.csv")

    if not result.metric_health.empty:
        result.metric_health.to_csv(output_dir / "metric_health.csv", index=False)

    if not result.source_health.empty:
        result.source_health.to_csv(output_dir / "source_health.csv", index=False)

    if result.category_breakdowns:
        category_dir = output_dir / "category_breakdowns"
        category_dir.mkdir(parents=True, exist_ok=True)
        for existing in category_dir.glob("*.csv"):
            existing.unlink()
        for target, frame in result.category_breakdowns.items():
            frame.to_csv(category_dir / f"{target}.csv")
