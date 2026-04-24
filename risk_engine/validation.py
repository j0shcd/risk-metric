from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

from .types import RiskOutput


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    errors: List[str]
    warnings: List[str]


def _check_index(series: pd.DataFrame, errors: List[str]) -> None:
    if not series.index.is_monotonic_increasing:
        errors.append("Output index is not monotonic increasing.")
    if series.index.has_duplicates:
        errors.append("Output index has duplicate timestamps.")


def _check_bounds(series: pd.DataFrame, errors: List[str]) -> None:
    bounded_columns = {
        "btc_risk_heat": (-1.0, 1.0),
        "btc_risk_attention": (0.0, 1.0),
        "total_market_risk_heat": (-1.0, 1.0),
        "total_market_risk_attention": (0.0, 1.0),
        "headline_attention": (0.0, 1.0),
        "headline_direction": (-1.0, 1.0),
        "confidence_score": (0.0, 1.0),
    }

    for column, (low, high) in bounded_columns.items():
        if column not in series.columns:
            errors.append(f"Missing output column: {column}")
            continue

        values = series[column].dropna()
        if values.empty:
            errors.append(f"Column has no usable values: {column}")
            continue

        if (values < low).any() or (values > high).any():
            errors.append(f"Column out of bounds [{low}, {high}]: {column}")


def _check_recent_signal_presence(series: pd.DataFrame, errors: List[str], lookback_days: int = 30) -> None:
    tail = series.tail(lookback_days)
    required_columns = [
        "btc_risk_heat",
        "btc_risk_attention",
        "headline_attention",
        "headline_direction",
        "confidence_score",
    ]
    for column in required_columns:
        if tail[column].dropna().empty:
            errors.append(f"No recent values in required column: {column}")


def _check_feature_reliability(feature_frames: dict, errors: List[str]) -> None:
    for name, frame in feature_frames.items():
        if "reliability" not in frame.columns:
            errors.append(f"Feature frame missing reliability column: {name}")
            continue
        rel = frame["reliability"].dropna()
        if rel.empty:
            continue
        if (rel < 0.0).any() or (rel > 1.0).any():
            errors.append(f"Feature reliability out of [0, 1] bounds: {name}")


def _check_output_staleness(
    series: pd.DataFrame,
    errors: List[str],
    columns: List[str],
    max_staleness_days: int = 7,
) -> None:
    now = pd.Timestamp.utcnow().tz_localize(None).normalize()
    for column in columns:
        values = series[column].dropna()
        if values.empty:
            continue
        last_date = values.index.max().normalize()
        staleness_days = int((now - last_date).days)
        if staleness_days > max_staleness_days:
            errors.append(
                f"Column appears stale ({staleness_days}d > {max_staleness_days}d): {column}"
            )


def _check_source_health(result: RiskOutput, errors: List[str]) -> None:
    if result.source_health.empty:
        errors.append("Missing source health report.")
        return

    source_health = result.source_health.copy()
    if "contract_passed" not in source_health.columns:
        source_health["contract_passed"] = True
    if "contract_issues" not in source_health.columns:
        source_health["contract_issues"] = ""

    required_sources = {"btc_price"}
    available_sources = set(
        source_health.loc[source_health["available"].fillna(False), "source"].astype(str).tolist()
    )
    missing = sorted(required_sources - available_sources)
    if missing:
        errors.append(f"Critical sources unavailable: {', '.join(missing)}")

    critical = source_health[source_health["source"].astype(str).isin(required_sources)]
    failing_critical = critical[~critical["contract_passed"].fillna(False)]
    if not failing_critical.empty:
        issues = []
        for row in failing_critical.itertuples(index=False):
            issues.append(f"{row.source}({row.contract_issues})")
        errors.append(f"Critical source contract failed: {', '.join(issues)}")


def _check_noncritical_source_contract_warnings(result: RiskOutput, warnings: List[str]) -> None:
    if result.source_health.empty:
        return

    source_health = result.source_health.copy()
    if "contract_passed" not in source_health.columns:
        return

    noncritical = source_health[~source_health["source"].astype(str).isin({"btc_price"})]
    failing = noncritical[~noncritical["contract_passed"].fillna(False)]
    for row in failing.itertuples(index=False):
        warnings.append(f"Non-critical source contract failed: {row.source} ({row.contract_issues})")


def _check_source_modes(result: RiskOutput, warnings: List[str]) -> None:
    if not result.source_modes:
        warnings.append("Source mode report missing; adapter provenance unavailable.")
        return

    modes = result.source_modes
    excluded_prefixes = ("onchain::supply_in_loss",)
    tracked = {k: v for k, v in modes.items() if not any(k.startswith(prefix) for prefix in excluded_prefixes)}

    api_like = 0
    fallback_like = 0
    unavailable = 0

    fallback_modes = {"local_cache", "coingecko_global_latest"}
    unavailable_modes = {"unavailable", "disabled", "unknown"}

    for mode in tracked.values():
        mode_str = str(mode)
        if mode_str in unavailable_modes:
            unavailable += 1
        elif mode_str in fallback_modes:
            fallback_like += 1
        else:
            api_like += 1

    warnings.append(
        f"Source modes: api={api_like}, fallback={fallback_like}, unavailable={unavailable}."
    )

    if unavailable > 0:
        unavailable_sources = sorted([source for source, mode in tracked.items() if str(mode) in unavailable_modes])
        preview = ", ".join(unavailable_sources[:3])
        suffix = "..." if len(unavailable_sources) > 3 else ""
        warnings.append(f"Some sources are unavailable ({preview}{suffix}); confidence may be reduced.")


def _check_metric_health(result: RiskOutput, errors: List[str]) -> None:
    if result.metric_health.empty:
        errors.append("Missing metric health report.")
        return

    required_targets = {"btc", "total_market"}
    available = result.metric_health[result.metric_health["available"].fillna(False)]
    available_targets = set(available["target"].astype(str).tolist())
    missing_targets = sorted(required_targets - available_targets)
    if missing_targets:
        errors.append(f"No available metrics for targets: {', '.join(missing_targets)}")


def build_walkforward_sanity_report(
    series: pd.DataFrame,
    price_column: str = "btc_price",
    heat_column: str = "btc_risk_heat",
    attention_column: str = "headline_attention",
) -> pd.DataFrame:
    required = {price_column, heat_column, attention_column}
    if not required.issubset(set(series.columns)):
        return pd.DataFrame(
            [
                {
                    "check": "required_columns_present",
                    "passed": False,
                    "value": np.nan,
                    "threshold": np.nan,
                    "comparator": "n/a",
                    "details": "Missing columns for sanity checks.",
                }
            ]
        )

    frame = series[[price_column, heat_column, attention_column]].dropna()
    if len(frame) < 365:
        return pd.DataFrame(
            [
                {
                    "check": "minimum_history_available",
                    "passed": False,
                    "value": float(len(frame)),
                    "threshold": 365.0,
                    "comparator": ">=",
                    "details": "Need at least 365 rows for walk-forward sanity checks.",
                }
            ]
        )

    price = frame[price_column]
    heat = frame[heat_column]
    attention = frame[attention_column]

    top_threshold = price.quantile(0.90)
    bottom_threshold = price.quantile(0.10)
    top_mask = price >= top_threshold
    bottom_mask = price <= bottom_threshold

    mid_low = price.quantile(0.40)
    mid_high = price.quantile(0.60)
    mid_mask = (price >= mid_low) & (price <= mid_high)

    one_year_roi = price.pct_change(365, fill_method=None)
    sideways_threshold = one_year_roi.abs().quantile(0.25)
    sideways_mask = one_year_roi.abs() <= sideways_threshold

    forward_return_90d = price.shift(-90) / price - 1.0
    corr_data = pd.concat([heat, forward_return_90d], axis=1).dropna()
    forward_corr = np.nan
    if len(corr_data) >= 50:
        forward_corr = corr_data.corr(method="spearman").iloc[0, 1]

    top_heat = heat[top_mask].mean()
    bottom_heat = heat[bottom_mask].mean()
    extremes_attention = attention[top_mask | bottom_mask].mean()
    mid_attention = attention[mid_mask].mean()
    sideways_attention_std = attention[sideways_mask].std(ddof=0)
    global_attention_std = attention.std(ddof=0)

    rows = [
        {
            "check": "heat_higher_in_top_vs_bottom_regime",
            "passed": bool(top_heat > bottom_heat),
            "value": float(top_heat - bottom_heat),
            "threshold": 0.0,
            "comparator": ">",
            "details": "Top-price regime should have higher heat than bottom regime.",
        },
        {
            "check": "attention_higher_at_extremes_vs_mid",
            "passed": bool(extremes_attention > mid_attention),
            "value": float(extremes_attention - mid_attention),
            "threshold": 0.0,
            "comparator": ">",
            "details": "Attention should be higher in extreme regimes than in mid regimes.",
        },
        {
            "check": "attention_dispersion_lower_in_sideways",
            "passed": bool(sideways_attention_std < global_attention_std),
            "value": float(sideways_attention_std - global_attention_std),
            "threshold": 0.0,
            "comparator": "<",
            "details": "Sideways periods should have lower attention dispersion.",
        },
        {
            "check": "heat_vs_forward_90d_return_spearman_nonpositive",
            "passed": bool(np.isnan(forward_corr) or forward_corr <= 0.0),
            "value": float(forward_corr) if not np.isnan(forward_corr) else np.nan,
            "threshold": 0.0,
            "comparator": "<=",
            "details": "Higher heat should not correlate positively with 90-day forward returns.",
        },
    ]

    return pd.DataFrame(rows)


def write_sanity_report(series: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    report = build_walkforward_sanity_report(series)
    output_dir.mkdir(parents=True, exist_ok=True)
    report.to_csv(output_dir / "sanity_report.csv", index=False)
    return report


def _sanity_is_actionable(series: pd.DataFrame) -> bool:
    required = {"confidence_score", "btc_risk_coverage", "total_market_risk_coverage"}
    if not required.issubset(set(series.columns)):
        return False

    tail = series.tail(30)
    if tail.empty:
        return False

    confidence = tail["confidence_score"].dropna().mean()
    btc_cov = tail["btc_risk_coverage"].dropna().mean()
    total_cov = tail["total_market_risk_coverage"].dropna().mean()

    if np.isnan(confidence) or np.isnan(btc_cov) or np.isnan(total_cov):
        return False

    return bool(confidence >= 0.6 and btc_cov >= 0.5 and total_cov >= 0.4)


def validate_output(result: RiskOutput) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []

    _check_index(result.series, errors)
    _check_bounds(result.series, errors)
    _check_recent_signal_presence(result.series, errors)
    _check_feature_reliability(result.feature_frames, errors)
    _check_output_staleness(
        result.series,
        errors,
        columns=[
            "btc_risk_heat",
            "btc_risk_attention",
            "total_market_risk_heat",
            "total_market_risk_attention",
            "headline_attention",
            "headline_direction",
            "confidence_score",
        ],
    )
    _check_source_health(result, errors)
    _check_noncritical_source_contract_warnings(result, warnings)
    _check_source_modes(result, warnings)
    _check_metric_health(result, errors)

    sanity_report = build_walkforward_sanity_report(result.series)
    if _sanity_is_actionable(result.series):
        for row in sanity_report.itertuples(index=False):
            if not bool(getattr(row, "passed")):
                warnings.append(f"Sanity check failed: {getattr(row, 'check')}")
    else:
        warnings.append("Sanity checks are informational only (insufficient recent coverage/confidence).")

    return ValidationResult(passed=not errors, errors=errors, warnings=warnings)
