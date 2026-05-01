from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from .calibration import calibrate_primary_outputs
from .benchmark import evaluate_benchmark
from .config import RuntimeConfig, load_runtime_config
from .cycle_model import build_cycle_model
from .diagnostics import build_metric_health, build_source_health
from .features import build_market_features, build_onchain_features, build_social_sentiment_features
from .normalization import build_feature_frame
from .scoring import MetricSpec, score_target
from .sources import (
    load_btc_price,
    load_cycle_market_context,
    load_fear_greed_index,
    load_onchain_metrics,
    load_social_metrics,
    load_total_market_cap,
)
from .types import FeatureBundle, RiskOutput


def _metric_specs_free_stable(include_total_market_fallback_proxies: bool) -> List[MetricSpec]:
    specs = [
        MetricSpec("btc_trend_extension_50d_350d", "price_structure", "btc", base_reliability=0.95, max_carry_days=7),
        MetricSpec("btc_running_roi_1y", "price_structure", "btc", base_reliability=0.95, max_carry_days=7),
        MetricSpec("btc_log_reg_deviation", "price_structure", "btc", base_reliability=0.95, max_carry_days=7),
        MetricSpec("btc_drawdown_from_ath", "price_structure", "btc", base_reliability=0.90, max_carry_days=3),
        MetricSpec(
            "btc_realized_vol_30d",
            "price_structure",
            "btc",
            base_reliability=0.85,
            max_carry_days=3,
            direction=-1.0,
        ),
        MetricSpec("total_trend_extension_50d_350d", "price_structure", "total_market", base_reliability=0.90, max_carry_days=7),
        MetricSpec("total_running_roi_1y", "price_structure", "total_market", base_reliability=0.90, max_carry_days=7),
        MetricSpec("total_log_reg_deviation", "price_structure", "total_market", base_reliability=0.90, max_carry_days=7),
        MetricSpec("total_drawdown_from_ath", "price_structure", "total_market", base_reliability=0.85, max_carry_days=3),
        MetricSpec(
            "total_realized_vol_30d",
            "price_structure",
            "total_market",
            base_reliability=0.80,
            max_carry_days=3,
            direction=-1.0,
        ),
        MetricSpec("total_trend_extension_50d_350d", "total_market_context", "btc", base_reliability=0.85, max_carry_days=7),
        MetricSpec("total_log_reg_deviation", "total_market_context", "btc", base_reliability=0.85, max_carry_days=7),
        MetricSpec("btc_dominance_proxy", "total_market_context", "both", base_reliability=0.60, max_carry_days=14),
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

    return specs


def _metric_specs_extended(cfg: RuntimeConfig, include_total_market_fallback_proxies: bool) -> List[MetricSpec]:
    specs = _metric_specs_free_stable(include_total_market_fallback_proxies=include_total_market_fallback_proxies)
    specs.extend(
        [
            MetricSpec("mvrv_z_score", "onchain", "both", base_reliability=0.85, max_carry_days=5),
            MetricSpec("puell_multiple", "onchain", "both", base_reliability=0.85, max_carry_days=5),
            MetricSpec("supply_in_profit", "onchain", "both", base_reliability=0.80, max_carry_days=5),
            MetricSpec("supply_in_loss", "onchain", "both", base_reliability=0.80, max_carry_days=5, direction=-1.0),
            MetricSpec("youtube_interest", "social", "both", base_reliability=0.60, max_carry_days=14),
            MetricSpec(
                "coinbase_app_rank_proxy",
                "social",
                "both",
                base_reliability=0.35,
                max_carry_days=14,
                experimental=True,
            ),
        ]
    )
    if cfg.enable_google_trends_source:
        specs.append(MetricSpec("google_trends_interest", "social", "both", base_reliability=0.50, max_carry_days=21))

    if not cfg.enable_coinbase_app_rank:
        specs = [spec for spec in specs if spec.name != "coinbase_app_rank_proxy"]

    return specs


def _metric_specs(cfg: RuntimeConfig, include_total_market_fallback_proxies: bool) -> List[MetricSpec]:
    if cfg.data_profile == "extended":
        return _metric_specs_extended(cfg, include_total_market_fallback_proxies=include_total_market_fallback_proxies)
    return _metric_specs_free_stable(include_total_market_fallback_proxies=include_total_market_fallback_proxies)


def _should_use_total_market_fallback_proxies(total_market_cap: pd.Series) -> bool:
    aligned = total_market_cap.astype(float)
    if aligned.empty:
        return True

    total_points = int(aligned.notna().sum())
    recent = aligned.tail(90)
    recent_coverage = float(recent.notna().mean()) if len(recent) else 0.0
    return bool(total_points < 365 or recent_coverage < 0.8)


def _source_mode_multiplier(mode: str) -> float:
    if mode in {
        "cmc_api",
        "coingecko_pro",
        "glassnode_api",
        "youtube_api",
        "google_trends_api",
        "alternative_me_api",
        "coingecko_free_api",
        "fred_graph_csv",
        "fred_api_json",
        "wikimedia_api",
        "pushshift_api",
    }:
        return 1.0
    if mode in {"derived_from_fred_api_json", "derived_from_fred_graph_csv"}:
        return 1.0
    if mode == "coinmetrics_community":
        return 0.90
    if mode == "coinmetrics_community_proxy":
        return 0.80
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
    if mode in {"future_upgrade", "future_upgrade_local_cache"}:
        return 0.0
    return 0.80


def _metric_source_modes(source_modes: Dict[str, str]) -> Dict[str, str]:
    total_mode = source_modes.get("total_market_cap", "unknown")
    onchain_supply_mode = source_modes.get("onchain::supply_in_profit", "unknown")

    return {
        "btc_trend_extension_50d_350d": source_modes.get("btc_price", "unknown"),
        "btc_running_roi_1y": source_modes.get("btc_price", "unknown"),
        "btc_log_reg_deviation": source_modes.get("btc_price", "unknown"),
        "btc_drawdown_from_ath": source_modes.get("btc_price", "unknown"),
        "btc_realized_vol_30d": source_modes.get("btc_price", "unknown"),
        "total_trend_extension_50d_350d": total_mode,
        "total_running_roi_1y": total_mode,
        "total_log_reg_deviation": total_mode,
        "total_drawdown_from_ath": total_mode,
        "total_realized_vol_30d": total_mode,
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


def _expanding_quantile_thresholds(
    series: pd.Series,
    *,
    quantile: float,
    min_history: int,
) -> pd.Series:
    values = series.astype(float)
    out = pd.Series(index=values.index, dtype=float)
    for i, idx in enumerate(values.index):
        history = values.iloc[: i + 1].dropna()
        if len(history) < max(int(min_history), 1):
            out.loc[idx] = np.nan
            continue
        out.loc[idx] = float(history.quantile(float(quantile)))
    return out


def _build_operational_alert_policy(
    scores: pd.Series,
    *,
    alert_rate: float,
    cooldown_months: int,
    min_history_months: int,
) -> pd.DataFrame:
    quantile = max(0.0, min(1.0, 1.0 - float(alert_rate)))
    threshold = _expanding_quantile_thresholds(scores, quantile=quantile, min_history=min_history_months)
    raw_alert = (scores >= threshold).fillna(False)

    alerted = pd.Series(False, index=scores.index, dtype=bool)
    cooldown_state = pd.Series(0, index=scores.index, dtype=int)

    cooldown = 0
    for idx in scores.index:
        if cooldown > 0:
            cooldown -= 1
            cooldown_state.loc[idx] = cooldown
            continue
        if bool(raw_alert.loc[idx]):
            alerted.loc[idx] = True
            cooldown = max(int(cooldown_months), 0)
            cooldown_state.loc[idx] = cooldown
        else:
            cooldown_state.loc[idx] = cooldown

    return pd.DataFrame(
        {
            "threshold": threshold.astype(float),
            "alert": alerted.astype(float),
            "cooldown_state": cooldown_state.astype(float),
        },
        index=scores.index,
    )


def _benchmark_snapshot(
    result_summary: pd.DataFrame,
    by_signal: pd.DataFrame,
    window_stats: pd.DataFrame,
    financial_summary: pd.DataFrame | None = None,
) -> Dict[str, Any]:
    return {
        "summary": result_summary.to_dict(orient="records") if not result_summary.empty else [],
        "by_signal": by_signal.to_dict(orient="records") if not by_signal.empty else [],
        "window_stats": window_stats.to_dict(orient="records") if not window_stats.empty else [],
        "financial_summary": financial_summary.to_dict(orient="records")
        if financial_summary is not None and not financial_summary.empty
        else [],
    }


def _load_benchmark_baseline(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _frame_from_records(records: Any) -> pd.DataFrame:
    if not isinstance(records, list):
        return pd.DataFrame()
    return pd.DataFrame(records)


def _delta_records(
    current: pd.DataFrame,
    baseline: pd.DataFrame,
    *,
    key_cols: List[str],
    metric_cols: List[str],
) -> List[Dict[str, Any]]:
    if current.empty:
        return []
    cur = current.copy()
    base = baseline.copy() if not baseline.empty else pd.DataFrame(columns=key_cols + metric_cols)
    for key in key_cols:
        if key not in base.columns:
            base[key] = np.nan
    merged = cur.merge(
        base[key_cols + [c for c in metric_cols if c in base.columns]],
        on=key_cols,
        how="left",
        suffixes=("_current", "_baseline"),
    )
    rows: List[Dict[str, Any]] = []
    for _, row in merged.iterrows():
        item: Dict[str, Any] = {k: row.get(k) for k in key_cols}
        for metric in metric_cols:
            cur_value = row.get(f"{metric}_current")
            base_value = row.get(f"{metric}_baseline")
            item[f"{metric}_current"] = float(cur_value) if pd.notna(cur_value) else np.nan
            item[f"{metric}_baseline"] = float(base_value) if pd.notna(base_value) else np.nan
            item[f"{metric}_delta"] = (
                float(cur_value - base_value)
                if pd.notna(cur_value) and pd.notna(base_value)
                else np.nan
            )
        rows.append(item)
    return rows


def _write_benchmark_baseline(path: Path, result: RiskOutput) -> None:
    payload = _benchmark_snapshot(
        result.benchmark_summary,
        result.benchmark_by_signal,
        result.benchmark_window_stats,
        result.financial_benchmark_summary,
    )
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def run_pipeline(cfg: RuntimeConfig | None = None) -> RiskOutput:
    runtime = cfg or load_runtime_config()

    btc_price = load_btc_price(runtime)
    index = btc_price.index

    total_market_cap = load_total_market_cap(runtime, index=index)
    use_total_market_fallback_proxies = _should_use_total_market_fallback_proxies(total_market_cap)
    metric_specs = _metric_specs(runtime, include_total_market_fallback_proxies=use_total_market_fallback_proxies)
    if runtime.data_profile == "extended":
        onchain_frame = load_onchain_metrics(runtime, index=index)
    else:
        onchain_frame = pd.DataFrame(index=index)
        onchain_frame.attrs["source_modes"] = {}
    fear_greed = load_fear_greed_index(runtime, index=index)
    if runtime.data_profile == "extended":
        social_frame = load_social_metrics(runtime, index=index)
    else:
        social_frame = pd.DataFrame(index=index)
        social_frame.attrs["source_modes"] = {}
    cycle_context = load_cycle_market_context(
        runtime,
        index=index,
        btc_price=btc_price,
        social_frame=social_frame,
    )

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
    cycle_modes = cycle_context.attrs.get("source_modes", {})
    for column in cycle_context.columns:
        source_modes[f"cycle::{column}"] = str(cycle_modes.get(f"cycle::{column}", "unknown"))

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
    output["btc_risk_heat"] = ((btc_score.heat + 1.0) / 2.0).clip(0.0, 1.0)
    output["btc_risk_attention"] = btc_score.attention
    output["btc_risk_confidence"] = btc_score.confidence
    output["btc_risk_coverage"] = btc_score.coverage

    output["total_market_risk_heat"] = ((total_score.heat + 1.0) / 2.0).clip(0.0, 1.0)
    output["total_market_risk_attention"] = total_score.attention
    output["total_market_risk_confidence"] = total_score.confidence
    output["total_market_risk_coverage"] = total_score.coverage

    btc_headline_weight = (0.7 * output["btc_risk_confidence"]).clip(lower=0.0)
    total_headline_weight = (0.3 * output["total_market_risk_confidence"]).clip(lower=0.0)
    weight_sum = (btc_headline_weight + total_headline_weight).replace({0.0: np.nan})
    btc_headline_mix = (btc_headline_weight / weight_sum).fillna(0.7).clip(0.0, 1.0)
    total_headline_mix = (total_headline_weight / weight_sum).fillna(0.3).clip(0.0, 1.0)

    output["headline_attention"] = (
        btc_headline_mix * output["btc_risk_attention"] + total_headline_mix * output["total_market_risk_attention"]
    ).clip(0.0, 1.0)

    output["headline_heat"] = (
        btc_headline_mix * output["btc_risk_heat"] + total_headline_mix * output["total_market_risk_heat"]
    ).clip(0.0, 1.0)

    output["confidence_score"] = (
        0.7 * output["btc_risk_confidence"] + 0.3 * output["total_market_risk_confidence"]
    ).clip(0.0, 1.0)
    output["headline_btc_mix_weight"] = btc_headline_mix
    output["headline_total_market_mix_weight"] = total_headline_mix

    output["btc_price"] = btc_price
    output["total_market_cap"] = total_market_cap

    cycle = build_cycle_model(
        cfg=runtime,
        btc_price=btc_price,
        onchain_frame=onchain_frame,
        context_frame=cycle_context,
        daily_index=index,
    )
    output = pd.concat([output, cycle.daily_projection], axis=1)

    output["trend_heat"] = output["headline_heat"].clip(0.0, 1.0)
    output["top_reversal_risk"] = output.get("cycle_p_frenzy", output["btc_risk_heat"]).clip(0.0, 1.0)
    output["bottom_reversal_risk"] = output.get("cycle_p_accumulation", (1.0 - output["btc_risk_heat"])).clip(0.0, 1.0)
    output["attention_score"] = output["headline_attention"].clip(0.0, 1.0)

    calibrated = calibrate_primary_outputs(output, cfg=runtime)
    output = calibrated.series
    output["headline_heat"] = (
        output["headline_btc_mix_weight"] * output["btc_risk_heat"]
        + output["headline_total_market_mix_weight"] * output["total_market_risk_heat"]
    ).clip(0.0, 1.0)

    fallback_monthly_heat = output["btc_risk_heat"].astype(float).resample(pd.offsets.MonthEnd()).last()
    top_monthly = output["top_reversal_risk"].astype(float).resample(pd.offsets.MonthEnd()).last().fillna(fallback_monthly_heat)
    bottom_monthly = output["bottom_reversal_risk"].astype(float).resample(pd.offsets.MonthEnd()).last().fillna(1.0 - fallback_monthly_heat)
    top_operational = _build_operational_alert_policy(
        top_monthly,
        alert_rate=float(runtime.operational_top_alert_rate),
        cooldown_months=int(runtime.operational_top_cooldown_months),
        min_history_months=int(runtime.operational_alert_min_history_months),
    )
    bottom_operational = _build_operational_alert_policy(
        bottom_monthly,
        alert_rate=float(runtime.operational_bottom_alert_rate),
        cooldown_months=int(runtime.operational_bottom_cooldown_months),
        min_history_months=int(runtime.operational_alert_min_history_months),
    )
    output["top_alert_operational"] = top_operational["alert"].reindex(output.index, method="ffill").fillna(0.0)
    output["bottom_alert_operational"] = bottom_operational["alert"].reindex(output.index, method="ffill").fillna(0.0)
    output["top_alert_threshold_operational"] = top_operational["threshold"].reindex(output.index, method="ffill")
    output["bottom_alert_threshold_operational"] = bottom_operational["threshold"].reindex(output.index, method="ffill")
    output["top_alert_cooldown_state_operational"] = (
        top_operational["cooldown_state"].reindex(output.index, method="ffill").fillna(0.0)
    )
    output["bottom_alert_cooldown_state_operational"] = (
        bottom_operational["cooldown_state"].reindex(output.index, method="ffill").fillna(0.0)
    )

    benchmark_result = evaluate_benchmark(
        runtime,
        monthly_price=output["btc_price"].astype(float).resample(pd.offsets.MonthEnd()).last(),
        signals={
            "trend_heat": output["trend_heat"].astype(float).resample(pd.offsets.MonthEnd()).last(),
            "top_reversal_risk": output["top_reversal_risk"].astype(float).resample(pd.offsets.MonthEnd()).last(),
            "bottom_reversal_risk": output["bottom_reversal_risk"].astype(float).resample(pd.offsets.MonthEnd()).last(),
            "attention_score": output["attention_score"].astype(float).resample(pd.offsets.MonthEnd()).last(),
        },
        calibration_metadata=calibrated.metadata,
    )

    baseline_path = runtime.output_dir / "benchmark_baseline.json"
    benchmark_baseline = _load_benchmark_baseline(baseline_path)
    baseline_summary = _frame_from_records(benchmark_baseline.get("summary"))
    baseline_by_signal = _frame_from_records(benchmark_baseline.get("by_signal"))
    baseline_window_stats = _frame_from_records(benchmark_baseline.get("window_stats"))
    baseline_financial = _frame_from_records(benchmark_baseline.get("financial_summary"))

    benchmark_deltas = {
        "summary": _delta_records(
            benchmark_result.summary,
            baseline_summary,
            key_cols=["kpi", "signal"],
            metric_cols=["expanding", "recent", "delta_recent_minus_expanding"],
        ),
        "by_signal": _delta_records(
            benchmark_result.by_signal,
            baseline_by_signal,
            key_cols=["window", "signal"],
            metric_cols=["auc", "pr_auc", "lead_recall_at_alert_rate", "false_alarm_rate"],
        ),
        "window_stats": _delta_records(
            benchmark_result.window_stats,
            baseline_window_stats,
            key_cols=["window", "side"],
            metric_cols=["auc", "pr_auc", "lead_recall_at_alert_rate", "false_alarm_rate", "event_coverage"],
        ),
        "financial_summary": _delta_records(
            cycle.financial_benchmark_summary,
            baseline_financial,
            key_cols=["strategy"],
            metric_cols=["cagr", "calmar", "max_drawdown", "total_return"],
        ),
    }

    regression_warnings: List[str] = []
    by_signal_deltas = pd.DataFrame(benchmark_deltas.get("by_signal", []))
    if {"window", "signal"}.issubset(set(by_signal_deltas.columns)):
        top_recent = by_signal_deltas[
            (by_signal_deltas["window"].astype(str) == "recent")
            & (by_signal_deltas["signal"].astype(str) == "top_reversal_risk")
        ]
        bottom_recent = by_signal_deltas[
            (by_signal_deltas["window"].astype(str) == "recent")
            & (by_signal_deltas["signal"].astype(str) == "bottom_reversal_risk")
        ]
    else:
        top_recent = pd.DataFrame()
        bottom_recent = pd.DataFrame()
    if not top_recent.empty:
        row = top_recent.iloc[0]
        recall_delta = row.get("lead_recall_at_alert_rate_delta")
        pr_delta = row.get("pr_auc_delta")
        far_delta = row.get("false_alarm_rate_delta")

        if pd.notna(recall_delta) and float(recall_delta) < float(runtime.benchmark_delta_warn_top_recall):
            regression_warnings.append(
                f"benchmark_top_recall_regression:{float(recall_delta):.4f}<{float(runtime.benchmark_delta_warn_top_recall):.4f}"
            )
        if pd.notna(pr_delta) and float(pr_delta) < float(runtime.benchmark_delta_warn_top_pr_auc):
            regression_warnings.append(
                f"benchmark_top_pr_auc_regression:{float(pr_delta):.4f}<{float(runtime.benchmark_delta_warn_top_pr_auc):.4f}"
            )
        if pd.notna(far_delta) and float(far_delta) > float(runtime.benchmark_delta_warn_top_false_alarm):
            regression_warnings.append(
                f"benchmark_top_false_alarm_regression:{float(far_delta):.4f}>{float(runtime.benchmark_delta_warn_top_false_alarm):.4f}"
            )
    if not bottom_recent.empty:
        row = bottom_recent.iloc[0]
        recall_delta = row.get("lead_recall_at_alert_rate_delta")
        pr_delta = row.get("pr_auc_delta")
        far_delta = row.get("false_alarm_rate_delta")
        if pd.notna(recall_delta) and float(recall_delta) < float(runtime.benchmark_delta_warn_bottom_recall):
            regression_warnings.append(
                f"benchmark_bottom_recall_regression:{float(recall_delta):.4f}<{float(runtime.benchmark_delta_warn_bottom_recall):.4f}"
            )
        if pd.notna(pr_delta) and float(pr_delta) < float(runtime.benchmark_delta_warn_bottom_pr_auc):
            regression_warnings.append(
                f"benchmark_bottom_pr_auc_regression:{float(pr_delta):.4f}<{float(runtime.benchmark_delta_warn_bottom_pr_auc):.4f}"
            )
        if pd.notna(far_delta) and float(far_delta) > float(runtime.benchmark_delta_warn_bottom_false_alarm):
            regression_warnings.append(
                f"benchmark_bottom_false_alarm_regression:{float(far_delta):.4f}>{float(runtime.benchmark_delta_warn_bottom_false_alarm):.4f}"
            )

    fin_deltas = pd.DataFrame(benchmark_deltas.get("financial_summary", []))
    dynamic = fin_deltas[fin_deltas["strategy"].astype(str) == "dynamic_dca"] if "strategy" in fin_deltas.columns else pd.DataFrame()
    if not dynamic.empty:
        row = dynamic.iloc[0]
        cagr_delta = row.get("cagr_delta")
        calmar_delta = row.get("calmar_delta")
        max_dd_delta = row.get("max_drawdown_delta")
        if pd.notna(cagr_delta) and float(cagr_delta) < float(runtime.benchmark_delta_warn_dynamic_dca_cagr):
            regression_warnings.append(
                f"benchmark_dynamic_dca_cagr_regression:{float(cagr_delta):.4f}<{float(runtime.benchmark_delta_warn_dynamic_dca_cagr):.4f}"
            )
        if pd.notna(calmar_delta) and float(calmar_delta) < float(runtime.benchmark_delta_warn_dynamic_dca_calmar):
            regression_warnings.append(
                f"benchmark_dynamic_dca_calmar_regression:{float(calmar_delta):.4f}<{float(runtime.benchmark_delta_warn_dynamic_dca_calmar):.4f}"
            )
        if pd.notna(max_dd_delta) and float(max_dd_delta) > float(runtime.benchmark_delta_warn_dynamic_dca_max_drawdown):
            regression_warnings.append(
                f"benchmark_dynamic_dca_max_drawdown_regression:{float(max_dd_delta):.4f}>{float(runtime.benchmark_delta_warn_dynamic_dca_max_drawdown):.4f}"
            )

    combined_benchmark_warnings = list(benchmark_result.warnings) + list(regression_warnings)

    as_of = pd.Timestamp.now("UTC").tz_localize(None).normalize()

    source_map = {
        "btc_price": btc_price,
        "total_market_cap": total_market_cap,
        "fear_greed_index": fear_greed,
    }
    for column in onchain_frame.columns:
        source_map[f"onchain::{column}"] = onchain_frame[column]
    for column in social_frame.columns:
        source_map[f"social::{column}"] = social_frame[column]
    for column in cycle_context.columns:
        source_map[f"cycle::{column}"] = cycle_context[column]

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
        cycle_feature_snapshots=cycle.feature_snapshots,
        cycle_regime_scores=cycle.regime_scores,
        cycle_signal_decisions=cycle.signal_decisions,
        cycle_backtest_report=cycle.backtest_report,
        financial_benchmark_summary=cycle.financial_benchmark_summary,
        financial_benchmark_curves=cycle.financial_benchmark_curves,
        cycle_metric_audit=cycle.metric_audit,
        cycle_migration_plan=cycle.migration_plan,
        benchmark_summary=benchmark_result.summary,
        benchmark_by_label=benchmark_result.by_label,
        benchmark_by_signal=benchmark_result.by_signal,
        benchmark_window_stats=benchmark_result.window_stats,
        benchmark_config=benchmark_result.config,
        benchmark_warnings=combined_benchmark_warnings,
        benchmark_baseline=benchmark_baseline,
        benchmark_deltas=benchmark_deltas,
        benchmark_regression_warnings=regression_warnings,
        operational_alert_policy={
            "top_alert_rate": float(runtime.operational_top_alert_rate),
            "bottom_alert_rate": float(runtime.operational_bottom_alert_rate),
            "top_cooldown_months": int(runtime.operational_top_cooldown_months),
            "bottom_cooldown_months": int(runtime.operational_bottom_cooldown_months),
            "min_history_months": int(runtime.operational_alert_min_history_months),
            "benchmark_alert_rate": float(runtime.benchmark_alert_rate),
            "cycle_financial_label_weight": float(runtime.cycle_financial_label_weight),
            "cycle_financial_kpi_weight": float(runtime.cycle_financial_kpi_weight),
        },
        calibration_metadata=calibrated.metadata,
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

    if not result.cycle_feature_snapshots.empty:
        result.cycle_feature_snapshots.to_csv(output_dir / "cycle_feature_snapshots_monthly.csv")
    if not result.cycle_regime_scores.empty:
        result.cycle_regime_scores.to_csv(output_dir / "cycle_regime_scores_monthly.csv")
    if not result.cycle_signal_decisions.empty:
        result.cycle_signal_decisions.to_csv(output_dir / "cycle_signal_decisions_monthly.csv")
    if not result.cycle_backtest_report.empty:
        result.cycle_backtest_report.to_csv(output_dir / "cycle_backtest_report.csv", index=False)
    if not result.financial_benchmark_summary.empty:
        result.financial_benchmark_summary.to_csv(output_dir / "financial_benchmark_summary.csv", index=False)
    if not result.financial_benchmark_curves.empty:
        result.financial_benchmark_curves.to_csv(output_dir / "financial_benchmark_curves_monthly.csv")
    if not result.cycle_metric_audit.empty:
        result.cycle_metric_audit.to_csv(output_dir / "cycle_metric_audit.csv", index=False)
    if result.cycle_migration_plan:
        (output_dir / "cycle_migration_plan.md").write_text(result.cycle_migration_plan + "\n", encoding="utf-8")
    if not result.benchmark_summary.empty:
        result.benchmark_summary.to_csv(output_dir / "benchmark_summary.csv", index=False)
    if not result.benchmark_by_label.empty:
        result.benchmark_by_label.to_csv(output_dir / "benchmark_by_label.csv", index=False)
    if not result.benchmark_by_signal.empty:
        result.benchmark_by_signal.to_csv(output_dir / "benchmark_by_signal.csv", index=False)
    if not result.benchmark_window_stats.empty:
        result.benchmark_window_stats.to_csv(output_dir / "benchmark_window_stats.csv", index=False)
    _write_benchmark_baseline(output_dir / "benchmark_baseline.json", result)
