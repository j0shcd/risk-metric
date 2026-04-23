from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

import numpy as np
import pandas as pd

from .types import FeatureBundle


@dataclass(frozen=True)
class MetricSpec:
    name: str
    category: str
    target: str
    base_reliability: float
    max_carry_days: int = 7
    direction: float = 1.0
    experimental: bool = False


@dataclass(frozen=True)
class TargetScore:
    heat: pd.Series
    attention: pd.Series
    confidence: pd.Series
    coverage: pd.Series
    category_breakdown: pd.DataFrame
    metric_breakdown: pd.DataFrame


def _series_or_nan(index: pd.Index) -> pd.Series:
    return pd.Series(np.nan, index=index, dtype=float)


def score_target(
    index: pd.DatetimeIndex,
    feature_bundles: Iterable[FeatureBundle],
    category_weights: Dict[str, float],
    target: str,
) -> TargetScore:
    bundles = [bundle for bundle in feature_bundles if bundle.target in {target, "both"}]

    if not bundles:
        nan_series = _series_or_nan(index)
        return TargetScore(
            heat=nan_series,
            attention=nan_series,
            confidence=nan_series,
            coverage=nan_series,
            category_breakdown=pd.DataFrame(index=index),
            metric_breakdown=pd.DataFrame(index=index),
        )

    category_bundles: Dict[str, List[FeatureBundle]] = {}
    for bundle in bundles:
        category_bundles.setdefault(bundle.category, []).append(bundle)

    category_heat = {}
    category_attention = {}
    category_reliability = {}
    category_coverage = {}
    category_gate = {}

    category_metric_heat = {}
    category_metric_attention = {}
    category_metric_reliability = {}

    for category, scoped_bundles in category_bundles.items():
        metric_names = [bundle.name for bundle in scoped_bundles]
        stacked_heat = pd.concat([bundle.frame["signed_heat"] for bundle in scoped_bundles], axis=1)
        stacked_attention = pd.concat([bundle.frame["attention"] for bundle in scoped_bundles], axis=1)
        stacked_reliability = pd.concat([bundle.frame["reliability"] for bundle in scoped_bundles], axis=1)
        stacked_heat.columns = metric_names
        stacked_attention.columns = metric_names
        stacked_reliability.columns = metric_names

        valid_count = stacked_heat.notna().sum(axis=1).astype(float)
        total = float(len(scoped_bundles))
        coverage = valid_count / total

        gate = pd.Series(1.0, index=index, dtype=float)
        under = coverage < 0.5
        gate.loc[under] = (coverage.loc[under] / 0.5).clip(lower=0.0, upper=1.0)

        weighted_heat_num = (stacked_heat * stacked_reliability).sum(axis=1, min_count=1)
        weighted_att_num = (stacked_attention * stacked_reliability).sum(axis=1, min_count=1)
        weighted_den = stacked_reliability.where(stacked_heat.notna()).sum(axis=1, min_count=1)

        heat = (weighted_heat_num / weighted_den).clip(-1.0, 1.0)
        attention = (weighted_att_num / weighted_den).clip(0.0, 1.0)
        reliability = (weighted_den / valid_count.replace({0.0: np.nan})).clip(0.0, 1.0)

        category_heat[category] = heat
        category_attention[category] = attention
        category_reliability[category] = reliability
        category_coverage[category] = coverage.clip(0.0, 1.0)
        category_gate[category] = gate
        category_metric_heat[category] = stacked_heat
        category_metric_attention[category] = stacked_attention
        category_metric_reliability[category] = stacked_reliability

    weighted_heat_num = pd.Series(0.0, index=index)
    weighted_heat_den = pd.Series(0.0, index=index)

    weighted_att_num = pd.Series(0.0, index=index)
    weighted_att_den = pd.Series(0.0, index=index)

    weighted_cov_num = pd.Series(0.0, index=index)
    weighted_cov_den = pd.Series(0.0, index=index)

    weighted_rel_num = pd.Series(0.0, index=index)
    weighted_rel_den = pd.Series(0.0, index=index)
    category_effective_weight = {}

    for category, base_weight in category_weights.items():
        if category not in category_heat:
            continue

        gate = category_gate[category]
        effective_weight = (base_weight * gate).fillna(0.0)

        heat_values = category_heat[category]
        att_values = category_attention[category]
        rel_values = category_reliability[category]
        cov_values = category_coverage[category]

        heat_mask = heat_values.notna()
        att_mask = att_values.notna()
        rel_mask = rel_values.notna()
        category_effective_weight[category] = effective_weight.where(heat_mask, 0.0)

        weighted_heat_num += effective_weight * heat_values.fillna(0.0)
        weighted_heat_den += effective_weight.where(heat_mask, 0.0)

        weighted_att_num += effective_weight * att_values.fillna(0.0)
        weighted_att_den += effective_weight.where(att_mask, 0.0)

        weighted_cov_num += base_weight * cov_values.fillna(0.0)
        weighted_cov_den += base_weight

        weighted_rel_num += effective_weight * rel_values.fillna(0.0)
        weighted_rel_den += effective_weight.where(rel_mask, 0.0)

    heat = (weighted_heat_num / weighted_heat_den.replace({0.0: np.nan})).clip(-1.0, 1.0)
    attention = (weighted_att_num / weighted_att_den.replace({0.0: np.nan})).clip(0.0, 1.0)

    coverage = (weighted_cov_num / weighted_cov_den.replace({0.0: np.nan})).clip(0.0, 1.0)
    reliability = (weighted_rel_num / weighted_rel_den.replace({0.0: np.nan})).clip(0.0, 1.0)

    confidence = (0.5 * coverage + 0.5 * reliability).clip(0.0, 1.0)

    category_weight_total = pd.Series(0.0, index=index)
    for category in category_heat.keys():
        category_weight_total += category_effective_weight.get(category, pd.Series(0.0, index=index)).fillna(0.0)

    breakdown_columns: Dict[str, pd.Series] = {}
    for category in sorted(category_heat.keys()):
        prefix = f"category_{category}"
        eff = category_effective_weight.get(category, pd.Series(0.0, index=index)).fillna(0.0)
        norm = eff / category_weight_total.replace({0.0: np.nan})
        norm = norm.clip(lower=0.0, upper=1.0)

        breakdown_columns[f"{prefix}_effective_weight"] = eff
        breakdown_columns[f"{prefix}_normalized_weight"] = norm
        breakdown_columns[f"{prefix}_heat"] = category_heat[category]
        breakdown_columns[f"{prefix}_attention"] = category_attention[category]
        breakdown_columns[f"{prefix}_coverage"] = category_coverage[category]
        breakdown_columns[f"{prefix}_reliability"] = category_reliability[category]
        breakdown_columns[f"{prefix}_heat_contribution"] = norm * category_heat[category]
        breakdown_columns[f"{prefix}_attention_contribution"] = norm * category_attention[category]

    breakdown_columns["effective_weight_total"] = category_weight_total
    breakdown_columns["active_category_count"] = (
        pd.concat(
            [series.notna().astype(float) for series in category_heat.values()],
            axis=1,
        ).sum(axis=1)
        if category_heat
        else 0.0
    )
    breakdown = pd.DataFrame(breakdown_columns, index=index)

    metric_columns: Dict[str, pd.Series] = {}
    metric_effective_weights: Dict[str, pd.Series] = {}
    metric_heat_series: Dict[str, pd.Series] = {}
    metric_attention_series: Dict[str, pd.Series] = {}

    for category in sorted(category_heat.keys()):
        category_eff = category_effective_weight.get(category, pd.Series(0.0, index=index)).fillna(0.0)
        metric_heat = category_metric_heat[category]
        metric_attention = category_metric_attention[category]
        metric_rel = category_metric_reliability[category]

        rel_masked = metric_rel.where(metric_heat.notna())
        rel_den = rel_masked.sum(axis=1, min_count=1)
        inner_weight = rel_masked.div(rel_den, axis=0)
        inner_weight = inner_weight.replace([np.inf, -np.inf], np.nan).fillna(0.0)

        for metric_name in metric_heat.columns:
            metric_prefix = f"metric_{metric_name}"
            eff = category_eff * inner_weight[metric_name]
            metric_effective_weights[metric_name] = eff
            metric_heat_series[metric_name] = metric_heat[metric_name]
            metric_attention_series[metric_name] = metric_attention[metric_name]

            metric_columns[f"{metric_prefix}_effective_weight"] = eff
            metric_columns[f"{metric_prefix}_category_inner_weight"] = inner_weight[metric_name]
            metric_columns[f"{metric_prefix}_heat"] = metric_heat[metric_name]
            metric_columns[f"{metric_prefix}_attention"] = metric_attention[metric_name]
            metric_columns[f"{metric_prefix}_reliability"] = metric_rel[metric_name]
            metric_columns[f"{metric_prefix}_coverage"] = metric_heat[metric_name].notna().astype(float)

    metric_weight_total = pd.Series(0.0, index=index)
    for weight in metric_effective_weights.values():
        metric_weight_total += weight.fillna(0.0)

    for metric_name in metric_effective_weights.keys():
        metric_prefix = f"metric_{metric_name}"
        eff = metric_effective_weights[metric_name].fillna(0.0)
        norm = eff / metric_weight_total.replace({0.0: np.nan})
        norm = norm.clip(lower=0.0, upper=1.0)
        metric_columns[f"{metric_prefix}_normalized_weight"] = norm
        metric_columns[f"{metric_prefix}_heat_contribution"] = norm * metric_heat_series[metric_name]
        metric_columns[f"{metric_prefix}_attention_contribution"] = (
            norm * metric_attention_series[metric_name]
        )

    metric_columns["effective_metric_weight_total"] = metric_weight_total
    metric_columns["active_metric_count"] = (
        pd.concat(
            [series.notna().astype(float) for series in category_metric_heat.values()],
            axis=1,
        ).sum(axis=1)
        if category_metric_heat
        else 0.0
    )
    metric_breakdown = pd.DataFrame(metric_columns, index=index)

    return TargetScore(
        heat=heat,
        attention=attention,
        confidence=confidence,
        coverage=coverage,
        category_breakdown=breakdown,
        metric_breakdown=metric_breakdown,
    )
