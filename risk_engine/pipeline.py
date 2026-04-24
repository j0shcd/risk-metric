from __future__ import annotations

from pathlib import Path
from typing import Dict, List

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


def _metric_specs(cfg: RuntimeConfig, include_total_market_fallback_proxies: bool) -> List[MetricSpec]:
    specs = [
        MetricSpec("btc_trend_extension_50d_350d", "price_structure", "btc", base_reliability=0.95, max_carry_days=7),
        MetricSpec("btc_running_roi_1y", "price_structure", "btc", base_reliability=0.95, max_carry_days=7),
        MetricSpec("btc_log_reg_deviation", "price_structure", "btc", base_reliability=0.95, max_carry_days=7),
        MetricSpec("total_trend_extension_50d_350d", "price_structure", "total_market", base_reliability=0.90, max_carry_days=7),
        MetricSpec("total_running_roi_1y", "price_structure", "total_market", base_reliability=0.90, max_carry_days=7),
        MetricSpec("total_log_reg_deviation", "price_structure", "total_market", base_reliability=0.90, max_carry_days=7),
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

    if include_total_market_fallback_proxies:
        specs.extend(
            [
                # Explicit fallback proxies only when total market-cap history is insufficient.
                MetricSpec(
                    "btc_trend_extension_50d_350d",
                    "price_structure",
                    "total_market",
                    base_reliability=0.35,
                    max_carry_days=7,
                ),
                MetricSpec(
                    "btc_running_roi_1y",
                    "price_structure",
                    "total_market",
                    base_reliability=0.35,
                    max_carry_days=7,
                ),
                MetricSpec(
                    "btc_log_reg_deviation",
                    "price_structure",
                    "total_market",
                    base_reliability=0.35,
                    max_carry_days=7,
                ),
            ]
        )

    if not cfg.enable_coinbase_app_rank:
        specs = [spec for spec in specs if spec.name != "coinbase_app_rank_proxy"]

    return specs


def _should_use_total_market_fallback_proxies(total_market_cap: pd.Series) -> bool:
    aligned = total_market_cap.astype(float)
    if aligned.empty:
        return True

    total_points = int(aligned.notna().sum())
    recent = aligned.tail(90)
    recent_coverage = float(recent.notna().mean()) if len(recent) else 0.0
    return bool(total_points < 365 or recent_coverage < 0.8)


def _source_mode_multiplier(mode: str) -> float:
    if mode in {"cmc_api", "coingecko_pro", "glassnode_api", "youtube_api", "google_trends_api", "alternative_me_api"}:
        return 1.0
    if mode == "coinmetrics_community":
        return 0.90
    if mode in {"apple_rss_top_free"}:
        return 0.80
    if mode in {"local_cache"}:
        return 0.75
    if mode in {"coingecko_global_latest"}:
        return 0.65
    if mode in {"local_csv"}:
        return 1.0
    if mode in {"unknown"}:
        return 0.80
    if mode in {"unavailable", "disabled"}:
        return 0.0
    return 0.80


def _metric_source_modes(source_modes: Dict[str, str]) -> Dict[str, str]:
    total_mode = source_modes.get("total_market_cap", "unknown")
    onchain_supply_mode = source_modes.get("onchain::supply_in_profit", "unknown")

    return {
        "btc_trend_extension_50d_350d": source_modes.get("btc_price", "unknown"),
        "btc_running_roi_1y": source_modes.get("btc_price", "unknown"),
        "btc_log_reg_deviation": source_modes.get("btc_price", "unknown"),
        "total_trend_extension_50d_350d": total_mode,
        "total_running_roi_1y": total_mode,
        "total_log_reg_deviation": total_mode,
        "btc_dominance_proxy": total_mode,
        "mvrv_z_score": source_modes.get("onchain::mvrv_z_score", "unknown"),
        "puell_multiple": source_modes.get("onchain::puell_multiple", "unknown"),
        "supply_in_profit": onchain_supply_mode,
        "supply_in_loss": onchain_supply_mode,
        "youtube_interest": source_modes.get("social::youtube_interest", "unknown"),
        "google_trends_interest": source_modes.get("social::google_trends_interest", "unknown"),
        "coinbase_app_rank_proxy": source_modes.get("social::coinbase_app_rank_proxy", "unknown"),
        "fear_greed_index": source_modes.get("fear_greed_index", "unknown"),
    }


def _metric_reliability_adjustments(metric_source_modes: Dict[str, str]) -> Dict[str, float]:
    return {metric: _source_mode_multiplier(mode) for metric, mode in metric_source_modes.items()}


def _build_feature_bundles(
    raw_features: pd.DataFrame,
    metric_specs: List[MetricSpec],
    reliability_adjustments: Dict[str, float],
) -> List[FeatureBundle]:
    bundles: List[FeatureBundle] = []
    for spec in metric_specs:
        if spec.name not in raw_features.columns:
            continue
        adjustment = reliability_adjustments.get(spec.name, 1.0)
        adjusted_base_reliability = float((spec.base_reliability * adjustment))
        adjusted_base_reliability = min(1.0, max(0.0, adjusted_base_reliability))

        frame = build_feature_frame(
            raw_series=raw_features[spec.name],
            base_reliability=adjusted_base_reliability,
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

    btc_price = load_btc_price(runtime)
    index = btc_price.index

    total_market_cap = load_total_market_cap(runtime, index=index)
    use_total_market_fallback_proxies = _should_use_total_market_fallback_proxies(total_market_cap)
    metric_specs = _metric_specs(runtime, include_total_market_fallback_proxies=use_total_market_fallback_proxies)
    onchain_frame = load_onchain_metrics(runtime, index=index)
    fear_greed = load_fear_greed_index(runtime, index=index)
    social_frame = load_social_metrics(runtime, index=index)

    source_modes = {
        "btc_price": "local_csv",
        "total_market_cap": str(total_market_cap.attrs.get("source_mode", "unknown")),
        "fear_greed_index": str(fear_greed.attrs.get("source_mode", "unknown")),
    }
    onchain_modes = onchain_frame.attrs.get("source_modes", {})
    for column in onchain_frame.columns:
        source_modes[f"onchain::{column}"] = str(onchain_modes.get(column, "unknown"))
    social_modes = social_frame.attrs.get("source_modes", {})
    for column in social_frame.columns:
        source_modes[f"social::{column}"] = str(social_modes.get(column, "unknown"))

    market_features = build_market_features(btc_price=btc_price, total_market_cap=total_market_cap)
    onchain_features = build_onchain_features(onchain_frame)
    social_features = build_social_sentiment_features(fear_greed=fear_greed, social_frame=social_frame)

    raw_features = pd.concat([market_features, onchain_features, social_features], axis=1)
    metric_source_modes = _metric_source_modes(source_modes=source_modes)
    reliability_adjustments = _metric_reliability_adjustments(metric_source_modes=metric_source_modes)

    bundles = _build_feature_bundles(
        raw_features=raw_features,
        metric_specs=metric_specs,
        reliability_adjustments=reliability_adjustments,
    )

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
        metric_source_modes=metric_source_modes,
        reliability_adjustments=reliability_adjustments,
    )
    source_health = build_source_health(source_map=source_map, as_of=as_of, lookback_days=30)

    return RiskOutput(
        series=output,
        feature_frames={bundle.name: bundle.frame for bundle in bundles},
        metric_health=metric_health,
        source_health=source_health,
        source_modes=source_modes,
        category_breakdowns={
            "btc": btc_score.category_breakdown,
            "total_market": total_score.category_breakdown,
        },
        metric_breakdowns={
            "btc": btc_score.metric_breakdown,
            "total_market": total_score.metric_breakdown,
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
    if result.source_modes:
        source_modes_frame = (
            pd.DataFrame(
                [{"source": source, "mode": mode} for source, mode in sorted(result.source_modes.items())]
            )
            .sort_values("source")
            .reset_index(drop=True)
        )
        source_modes_frame.to_csv(output_dir / "source_modes.csv", index=False)

    if result.category_breakdowns:
        category_dir = output_dir / "category_breakdowns"
        category_dir.mkdir(parents=True, exist_ok=True)
        for existing in category_dir.glob("*.csv"):
            existing.unlink()
        for target, frame in result.category_breakdowns.items():
            frame.to_csv(category_dir / f"{target}.csv")

    if result.metric_breakdowns:
        metric_dir = output_dir / "metric_breakdowns"
        metric_dir.mkdir(parents=True, exist_ok=True)
        for existing in metric_dir.glob("*.csv"):
            existing.unlink()
        for target, frame in result.metric_breakdowns.items():
            frame.to_csv(metric_dir / f"{target}.csv")
