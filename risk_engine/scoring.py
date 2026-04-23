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
        )

    category_frames: Dict[str, List[pd.DataFrame]] = {}
    for bundle in bundles:
        category_frames.setdefault(bundle.category, []).append(bundle.frame)

    category_heat = {}
    category_attention = {}
    category_reliability = {}
    category_coverage = {}
    category_gate = {}

    for category, frames in category_frames.items():
        stacked_heat = pd.concat([f["signed_heat"] for f in frames], axis=1)
        stacked_attention = pd.concat([f["attention"] for f in frames], axis=1)
        stacked_reliability = pd.concat([f["reliability"] for f in frames], axis=1)
        column_ids = list(range(stacked_heat.shape[1]))
        stacked_heat.columns = column_ids
        stacked_attention.columns = column_ids
        stacked_reliability.columns = column_ids

        valid_count = stacked_heat.notna().sum(axis=1).astype(float)
        total = float(len(frames))
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

    breakdown = pd.DataFrame(index=index)
    for category in sorted(category_heat.keys()):
        prefix = f"category_{category}"
        eff = category_effective_weight.get(category, pd.Series(0.0, index=index)).fillna(0.0)
        norm = eff / category_weight_total.replace({0.0: np.nan})
        norm = norm.clip(lower=0.0, upper=1.0)

        breakdown[f"{prefix}_effective_weight"] = eff
        breakdown[f"{prefix}_normalized_weight"] = norm
        breakdown[f"{prefix}_heat"] = category_heat[category]
        breakdown[f"{prefix}_attention"] = category_attention[category]
        breakdown[f"{prefix}_coverage"] = category_coverage[category]
        breakdown[f"{prefix}_reliability"] = category_reliability[category]
        breakdown[f"{prefix}_heat_contribution"] = norm * category_heat[category]
        breakdown[f"{prefix}_attention_contribution"] = norm * category_attention[category]

    breakdown["effective_weight_total"] = category_weight_total
    breakdown["active_category_count"] = (
        pd.concat(
            [series.notna().astype(float) for series in category_heat.values()],
            axis=1,
        ).sum(axis=1)
        if category_heat
        else 0.0
    )

    return TargetScore(
        heat=heat,
        attention=attention,
        confidence=confidence,
        coverage=coverage,
        category_breakdown=breakdown,
    )
