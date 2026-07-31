from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from risk_engine.benchmark import _auc, _pr_auc

from .config import EvaluationConfig
from .walkforward import _binary_alert_metrics, _expanding_alerts


@dataclass(frozen=True)
class WalkForwardRobustnessResult:
    nulls: pd.DataFrame
    baselines: pd.DataFrame
    by_label: pd.DataFrame
    config: Dict[str, Any]
    warnings: List[str]


def _stable_int(value: str) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def _empirical_p_right(observed: float, null_values: pd.Series) -> float:
    values = pd.to_numeric(null_values, errors="coerce").dropna()
    if not np.isfinite(observed) or values.empty:
        return float("nan")
    return float((1 + int((values >= observed).sum())) / (1 + len(values)))


def _benjamini_hochberg(p_values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(p_values, errors="coerce")
    adjusted = pd.Series(np.nan, index=numeric.index, dtype=float)
    valid = numeric.dropna().sort_values()
    m = len(valid)
    if m == 0:
        return adjusted

    ranked = valid.to_frame("p")
    ranked["rank"] = np.arange(1, m + 1, dtype=float)
    ranked["raw_q"] = ranked["p"] * float(m) / ranked["rank"]
    ranked["q"] = ranked["raw_q"][::-1].cummin()[::-1].clip(upper=1.0)
    adjusted.loc[ranked.index] = ranked["q"]
    return adjusted


def _select_shifts(n: int, horizon: int, n_null: int, seed: int) -> List[int]:
    if n <= 2:
        return []
    min_shift = max(int(horizon), 1)
    candidates = [shift for shift in range(1, n) if min(shift, n - shift) >= min_shift]
    if not candidates:
        return []
    if len(candidates) <= n_null:
        return candidates
    rng = np.random.default_rng(seed)
    selected = rng.choice(np.asarray(candidates, dtype=int), size=int(n_null), replace=False)
    return sorted(int(item) for item in selected.tolist())


def _metric_values(scores: pd.Series, labels: pd.Series) -> Dict[str, float]:
    return {
        "auc": _auc(scores, labels),
        "pr_auc": _pr_auc(scores, labels),
    }


def _event_concentration(ordered: pd.DataFrame, frame: pd.DataFrame, config: EvaluationConfig) -> Dict[str, Any]:
    label_values = pd.to_numeric(frame["label"], errors="coerce")
    events = frame.loc[label_values == 1]
    event_count = int(events.shape[0])
    if event_count == 0:
        return {
            "event_year_count": 0,
            "max_event_year_share": np.nan,
            "event_concentration_hhi": np.nan,
            "dominant_event_year": "",
            "passes_regime_concentration_gate": False,
            "regime_concentration_method": "calendar_year_event_concentration",
        }

    dates = pd.to_datetime(ordered.loc[events.index, "decision_date"], errors="coerce")
    years = dates.dt.year.dropna().astype(int)
    if years.empty:
        return {
            "event_year_count": 0,
            "max_event_year_share": np.nan,
            "event_concentration_hhi": np.nan,
            "dominant_event_year": "",
            "passes_regime_concentration_gate": False,
            "regime_concentration_method": "calendar_year_event_concentration",
        }

    counts = years.value_counts()
    shares = counts.astype(float) / float(event_count)
    max_share = float(shares.max())
    year_count = int(counts.shape[0])
    return {
        "event_year_count": year_count,
        "max_event_year_share": max_share,
        "event_concentration_hhi": float((shares**2).sum()),
        "dominant_event_year": str(int(counts.idxmax())),
        "passes_regime_concentration_gate": bool(
            year_count >= int(config.claim_gates.min_event_years)
            and max_share <= float(config.claim_gates.max_event_year_share)
        ),
        "regime_concentration_method": "calendar_year_event_concentration",
    }


def evaluate_walkforward_robustness(
    by_fold: pd.DataFrame,
    by_label: pd.DataFrame,
    config: EvaluationConfig,
) -> WalkForwardRobustnessResult:
    if by_fold.empty or by_label.empty:
        return WalkForwardRobustnessResult(
            nulls=pd.DataFrame(),
            baselines=pd.DataFrame(),
            by_label=by_label.copy(),
            config={"enabled": False},
            warnings=["walkforward_robustness_unavailable:missing_walkforward_inputs"],
        )

    n_null = 31 if config.smoke_mode else 199
    null_rows: List[Dict[str, Any]] = []
    baseline_rows: List[Dict[str, Any]] = []
    summary_rows: List[Dict[str, Any]] = []

    required = {"signal", "label_id", "decision_date", "score_value", "test_label", "horizon_months"}
    missing = sorted(required - set(by_fold.columns))
    if missing:
        return WalkForwardRobustnessResult(
            nulls=pd.DataFrame(),
            baselines=pd.DataFrame(),
            by_label=by_label.copy(),
            config={"enabled": False, "missing_columns": missing},
            warnings=["walkforward_robustness_unavailable:missing_columns"],
        )

    for (signal, label_id), group in by_fold.groupby(["signal", "label_id"], dropna=False):
        ordered = group.sort_values("decision_date").copy()
        frame = pd.DataFrame(
            {
                "score": pd.to_numeric(ordered["score_value"], errors="coerce"),
                "label": pd.to_numeric(ordered["test_label"], errors="coerce"),
            }
        ).dropna()
        if frame.empty:
            continue

        horizon = int(pd.to_numeric(ordered["horizon_months"], errors="coerce").dropna().iloc[0])
        side = str(ordered.get("side", pd.Series([""])).iloc[0])
        family = str(ordered.get("family", pd.Series([""])).iloc[0])
        confirmatory = bool(ordered.get("confirmatory", pd.Series([True])).fillna(True).astype(bool).iloc[0])
        label_match = by_label[
            by_label["signal"].astype(str).eq(str(signal))
            & by_label["label_id"].astype(str).eq(str(label_id))
        ]
        passes_sample_gate = bool(
            not label_match.empty and label_match["passes_sample_gate"].fillna(False).astype(bool).iloc[0]
        ) if "passes_sample_gate" in label_match.columns else False
        observed = _metric_values(frame["score"], frame["label"])
        concentration = _event_concentration(ordered, frame, config)
        shifts = _select_shifts(
            len(frame),
            horizon=horizon,
            n_null=n_null,
            seed=int(config.seed) + _stable_int(f"{signal}:{label_id}:shift"),
        )
        for iteration, shift in enumerate(shifts):
            shifted = pd.Series(np.roll(frame["score"].to_numpy(), shift), index=frame.index, dtype=float)
            null_values = _metric_values(shifted, frame["label"])
            for metric_name, null_value in null_values.items():
                row = {
                    "signal": signal,
                    "confirmatory": confirmatory,
                    "label_id": label_id,
                    "family": family,
                    "side": side,
                    "horizon_months": horizon,
                    "metric": metric_name,
                    "observed_value": observed.get(metric_name),
                    "null_method": "circular_shift",
                    "null_iteration": int(iteration),
                    "shift_months": int(shift),
                    "seed": int(config.seed),
                    "null_value": null_value,
                    "n_obs": int(frame.shape[0]),
                    "n_events": int((frame["label"].astype(int) == 1).sum()),
                    "effective_observations": int(np.floor(frame.shape[0] / max(horizon, 1))),
                }
                null_rows.append(row)

        baseline_seed = int(config.seed) + _stable_int(f"{label_id}:random_uniform_seeded")
        rng = np.random.default_rng(baseline_seed)
        random_scores = pd.Series(rng.uniform(0.0, 1.0, size=len(frame)), index=frame.index, dtype=float)
        alerts, _ = _expanding_alerts(random_scores, alert_rate=0.20, min_history_months=min(36, max(1, len(frame) // 2)))
        baseline_metrics = {
            **_metric_values(random_scores, frame["label"]),
            **_binary_alert_metrics(alerts, frame["label"]),
        }
        baseline_rows.append(
            {
                "baseline_signal": "random_uniform_seeded",
                "signal": signal,
                "confirmatory": confirmatory,
                "label_id": label_id,
                "family": family,
                "side": side,
                "horizon_months": horizon,
                "baseline_method": "random_uniform_seeded",
                "seed": baseline_seed,
                "n_obs": int(frame.shape[0]),
                "n_events": int((frame["label"].astype(int) == 1).sum()),
                **baseline_metrics,
            }
        )

        null_frame = pd.DataFrame(null_rows)
        if not null_frame.empty and {"signal", "label_id"}.issubset(null_frame.columns):
            pair_null = null_frame[(null_frame["signal"] == signal) & (null_frame["label_id"] == label_id)]
        else:
            pair_null = pd.DataFrame(columns=["metric", "null_value"])
        auc_null = pair_null[pair_null["metric"] == "auc"]["null_value"]
        pr_null = pair_null[pair_null["metric"] == "pr_auc"]["null_value"]
        auc_p = _empirical_p_right(float(observed.get("auc", np.nan)), auc_null)
        pr_p = _empirical_p_right(float(observed.get("pr_auc", np.nan)), pr_null)
        random_auc = float(baseline_metrics.get("auc", np.nan))
        random_pr_auc = float(baseline_metrics.get("pr_auc", np.nan))
        summary_rows.append(
            {
                "signal": signal,
                "confirmatory": confirmatory,
                "label_id": label_id,
                "null_method": "circular_shift",
                "null_iterations": int(len(shifts)),
                "auc_null_mean": float(auc_null.mean()) if not auc_null.empty else np.nan,
                "auc_null_p95": float(auc_null.quantile(0.95)) if not auc_null.empty else np.nan,
                "auc_empirical_p_right": auc_p,
                "pr_auc_empirical_p_right": pr_p,
                "p_value_method": "empirical_circular_shift",
                "p_value_resolution": float(1.0 / (len(shifts) + 1)) if shifts else np.nan,
                "p_value_caveat": "overlapping_horizons_autocorrelation_sparse_events",
                "is_formal_significance": False,
                "multiple_testing_corrected": False,
                "random_auc": random_auc,
                "random_pr_auc": random_pr_auc,
                "beats_random_auc": bool(np.isfinite(observed.get("auc", np.nan)) and np.isfinite(random_auc) and observed["auc"] > random_auc),
                "passes_sample_gate": passes_sample_gate,
                **concentration,
            }
        )

    nulls = pd.DataFrame(null_rows)
    baselines = pd.DataFrame(baseline_rows)
    summary = pd.DataFrame(summary_rows)
    if not summary.empty:
        alpha = float(config.claim_gates.fdr_alpha)
        confirmatory_mask = summary.get("confirmatory", pd.Series(True, index=summary.index)).fillna(True).astype(bool)
        summary["auc_fdr_q_value"] = np.nan
        summary["pr_auc_fdr_q_value"] = np.nan
        summary.loc[confirmatory_mask, "auc_fdr_q_value"] = _benjamini_hochberg(
            summary.loc[confirmatory_mask, "auc_empirical_p_right"]
        )
        summary.loc[confirmatory_mask, "pr_auc_fdr_q_value"] = _benjamini_hochberg(
            summary.loc[confirmatory_mask, "pr_auc_empirical_p_right"]
        )
        summary["fdr_alpha"] = alpha
        summary["auc_passes_fdr"] = pd.to_numeric(summary["auc_fdr_q_value"], errors="coerce") <= alpha
        summary["pr_auc_passes_fdr"] = pd.to_numeric(summary["pr_auc_fdr_q_value"], errors="coerce") <= alpha
        summary["multiple_testing_corrected"] = confirmatory_mask
        summary["multiple_testing_method"] = np.where(
            confirmatory_mask,
            "benjamini_hochberg_confirmatory_walkforward_label_rows",
            "not_applicable_non_confirmatory_metric",
        )
        summary["survives_circular_shift_null"] = (
            (pd.to_numeric(summary["auc_empirical_p_right"], errors="coerce") <= alpha)
            & summary["auc_passes_fdr"].fillna(False)
            & summary["beats_random_auc"].fillna(False)
        )
        summary["passes_initial_robustness_gates"] = (
            summary["survives_circular_shift_null"].fillna(False)
            & summary["passes_regime_concentration_gate"].fillna(False)
            & summary["passes_sample_gate"].fillna(False)
        )
    enriched = by_label.copy()
    if not summary.empty:
        enriched = enriched.merge(
            summary.drop(columns=["confirmatory"], errors="ignore"),
            how="left",
            on=["signal", "label_id"],
        )
        robustness_warning_count = (
            enriched["survives_circular_shift_null"].fillna(False).map(lambda value: 0 if value else 1)
            + enriched["multiple_testing_corrected"].fillna(False).map(lambda value: 0 if value else 1)
            + enriched["passes_regime_concentration_gate"].fillna(False).map(lambda value: 0 if value else 1)
        )
        enriched["robustness_warning_count"] = robustness_warning_count.astype(int)

    warnings: List[str] = []
    if nulls.empty:
        warnings.append("walkforward_nulls_unavailable:no_null_rows")
    if baselines.empty:
        warnings.append("walkforward_baselines_unavailable:no_baseline_rows")
    return WalkForwardRobustnessResult(
        nulls=nulls.sort_values(["signal", "label_id", "metric", "null_iteration"]).reset_index(drop=True)
        if not nulls.empty
        else nulls,
        baselines=baselines.sort_values(["signal", "label_id"]).reset_index(drop=True)
        if not baselines.empty
        else baselines,
        by_label=enriched.sort_values(["signal", "label_id"]).reset_index(drop=True),
        config={
            "enabled": True,
            "null_method": "circular_shift",
            "n_null_target": int(n_null),
            "baseline_method": "random_uniform_seeded",
            "seed": int(config.seed),
            "multiple_testing_corrected": True,
            "multiple_testing_method": "benjamini_hochberg_confirmatory_walkforward_label_rows",
            "fdr_alpha": float(config.claim_gates.fdr_alpha),
            "regime_concentration_method": "calendar_year_event_concentration",
            "max_event_year_share": float(config.claim_gates.max_event_year_share),
            "min_event_years": int(config.claim_gates.min_event_years),
        },
        warnings=warnings,
    )
