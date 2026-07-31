from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from risk_engine.benchmark import _auc, _pr_auc

from .config import EvaluationConfig
from .walkforward import _month_end_series


@dataclass(frozen=True)
class StrengthMappingResult:
    degraded_data: pd.DataFrame
    regime_results: pd.DataFrame
    rolling_stability: pd.DataFrame
    by_label: pd.DataFrame
    config: Dict[str, Any]
    warnings: List[str]


def _market_regimes(price: pd.Series) -> pd.Series:
    monthly = _month_end_series(price)
    ret_12m = monthly.pct_change(12, fill_method=None)
    drawdown = monthly / monthly.cummax().replace({0.0: np.nan}) - 1.0
    vol_6m = monthly.pct_change(fill_method=None).rolling(6, min_periods=3).std()
    regimes = pd.Series("unknown", index=monthly.index, dtype=object)
    regimes.loc[(ret_12m > 0.30) & (drawdown > -0.25)] = "bull_trend"
    regimes.loc[(drawdown <= -0.40) | (ret_12m < -0.30)] = "bear_drawdown"
    regimes.loc[(ret_12m.abs() <= 0.30) & (vol_6m <= vol_6m.expanding().median())] = "sideways_quiet"
    regimes.loc[(ret_12m.abs() <= 0.30) & (vol_6m > vol_6m.expanding().median())] = "sideways_volatile"
    return regimes


def _degraded_scores(scores: pd.Series, scenario: str, seed: int) -> pd.Series:
    clean = pd.to_numeric(scores, errors="coerce").astype(float)
    if scenario == "missing_20pct_ffill":
        out = clean.copy()
        if len(out) > 0:
            mask = (np.arange(len(out)) % 5) == 0
            out.iloc[mask] = np.nan
        return out.ffill()
    if scenario == "stale_3m":
        return clean.shift(3).ffill()
    if scenario == "noise_10pct":
        rng = np.random.default_rng(seed)
        noise = pd.Series(rng.normal(0.0, 0.10, size=len(clean)), index=clean.index)
        return (clean + noise).clip(0.0, 1.0)
    return clean


def evaluate_strength_mapping(
    series: pd.DataFrame,
    by_fold: pd.DataFrame,
    by_label: pd.DataFrame,
    config: EvaluationConfig,
) -> StrengthMappingResult:
    if by_fold.empty or by_label.empty or "btc_price" not in series.columns:
        return StrengthMappingResult(
            degraded_data=pd.DataFrame(),
            regime_results=pd.DataFrame(),
            rolling_stability=pd.DataFrame(),
            by_label=by_label.copy(),
            config={"enabled": False},
            warnings=["strength_mapping_unavailable:missing_inputs"],
        )

    required = {"signal", "label_id", "decision_date", "score_value", "test_label", "horizon_months"}
    missing = sorted(required - set(by_fold.columns))
    if missing:
        return StrengthMappingResult(
            degraded_data=pd.DataFrame(),
            regime_results=pd.DataFrame(),
            rolling_stability=pd.DataFrame(),
            by_label=by_label.copy(),
            config={"enabled": False, "missing_columns": missing},
            warnings=["strength_mapping_unavailable:missing_columns"],
        )

    regimes = _market_regimes(series["btc_price"])
    scenarios = ["missing_20pct_ffill", "stale_3m", "noise_10pct"]
    degraded_rows: List[Dict[str, Any]] = []
    regime_rows: List[Dict[str, Any]] = []
    rolling_rows: List[Dict[str, Any]] = []
    summary_rows: List[Dict[str, Any]] = []
    rolling_window = 36 if config.smoke_mode else 60
    step = 12

    for (signal, label_id), group in by_fold.groupby(["signal", "label_id"], dropna=False):
        ordered = group.sort_values("decision_date").reset_index(drop=True)
        frame = pd.DataFrame(
            {
                "date": pd.to_datetime(ordered["decision_date"], errors="coerce"),
                "score": pd.to_numeric(ordered["score_value"], errors="coerce"),
                "label": pd.to_numeric(ordered["test_label"], errors="coerce"),
            }
        ).dropna()
        if frame.empty:
            continue
        family = str(ordered.get("family", pd.Series([""])).iloc[0])
        side = str(ordered.get("side", pd.Series([""])).iloc[0])
        confirmatory = bool(ordered.get("confirmatory", pd.Series([True])).fillna(True).astype(bool).iloc[0])
        horizon = int(pd.to_numeric(ordered["horizon_months"], errors="coerce").dropna().iloc[0])
        observed_auc = _auc(frame["score"], frame["label"])

        scenario_deltas: List[float] = []
        for scenario in scenarios:
            degraded = _degraded_scores(frame["score"], scenario, seed=int(config.seed) + len(degraded_rows) + 5003)
            auc = _auc(degraded, frame["label"])
            delta = float(auc - observed_auc) if np.isfinite(auc) and np.isfinite(observed_auc) else np.nan
            if np.isfinite(delta):
                scenario_deltas.append(delta)
            degraded_rows.append(
                {
                    "signal": signal,
                    "confirmatory": confirmatory,
                    "label_id": label_id,
                    "family": family,
                    "side": side,
                    "horizon_months": horizon,
                    "scenario": scenario,
                    "observed_auc": observed_auc,
                    "degraded_auc": auc,
                    "auc_delta": delta,
                    "degraded_pr_auc": _pr_auc(degraded, frame["label"]),
                    "n_obs": int(frame.shape[0]),
                    "n_events": int((frame["label"].astype(int) == 1).sum()),
                }
            )

        with_regime = frame.copy()
        with_regime["regime"] = regimes.reindex(pd.DatetimeIndex(with_regime["date"])).to_numpy()
        for regime, regime_frame in with_regime.groupby("regime", dropna=False):
            n_events = int((regime_frame["label"].astype(int) == 1).sum())
            n_non_events = int((regime_frame["label"].astype(int) == 0).sum())
            eligible = bool(n_events >= 3 and n_non_events >= 3)
            regime_rows.append(
                {
                    "signal": signal,
                    "confirmatory": confirmatory,
                    "label_id": label_id,
                    "family": family,
                    "side": side,
                    "horizon_months": horizon,
                    "regime": regime,
                    "n_obs": int(regime_frame.shape[0]),
                    "n_events": n_events,
                    "n_non_events": n_non_events,
                    "auc": _auc(regime_frame["score"], regime_frame["label"]) if eligible else np.nan,
                    "pr_auc": _pr_auc(regime_frame["score"], regime_frame["label"]) if eligible else np.nan,
                    "regime_result_eligible": eligible,
                    "regime_metric_scope": "eligible" if eligible else "underpowered_descriptive_only",
                }
            )

        auc_windows: List[float] = []
        if frame.shape[0] >= rolling_window:
            for start in range(0, frame.shape[0] - rolling_window + 1, step):
                window = frame.iloc[start : start + rolling_window]
                auc = _auc(window["score"], window["label"])
                auc_windows.append(auc)
                rolling_rows.append(
                    {
                        "signal": signal,
                        "confirmatory": confirmatory,
                        "label_id": label_id,
                        "family": family,
                        "side": side,
                        "horizon_months": horizon,
                        "window_start": window["date"].iloc[0],
                        "window_end": window["date"].iloc[-1],
                        "n_obs": int(window.shape[0]),
                        "n_events": int((window["label"].astype(int) == 1).sum()),
                        "auc": auc,
                    }
                )

        finite_windows = [value for value in auc_windows if np.isfinite(value)]
        summary_rows.append(
            {
                "signal": signal,
                "confirmatory": confirmatory,
                "label_id": label_id,
                "worst_degraded_auc_delta": float(min(scenario_deltas)) if scenario_deltas else np.nan,
                "rolling_auc_min": float(min(finite_windows)) if finite_windows else np.nan,
                "rolling_auc_max": float(max(finite_windows)) if finite_windows else np.nan,
                "rolling_auc_range": float(max(finite_windows) - min(finite_windows)) if finite_windows else np.nan,
                "degraded_data_evaluable": bool(scenario_deltas),
                "rolling_stability_evaluable": bool(finite_windows),
                "passes_degraded_data_gate": bool(scenario_deltas and min(scenario_deltas) >= -0.10),
                "passes_rolling_stability_gate": bool(
                    finite_windows and (max(finite_windows) - min(finite_windows)) <= 0.30
                ),
            }
        )

    degraded = pd.DataFrame(degraded_rows)
    regime_results = pd.DataFrame(regime_rows)
    rolling = pd.DataFrame(rolling_rows)
    summary = pd.DataFrame(summary_rows)
    enriched = by_label.copy()
    if not summary.empty:
        enriched = enriched.merge(
            summary.drop(columns=["confirmatory"], errors="ignore"),
            how="left",
            on=["signal", "label_id"],
        )

    warnings: List[str] = []
    if degraded.empty:
        warnings.append("degraded_data_unavailable:no_rows")
    if regime_results.empty:
        warnings.append("regime_results_unavailable:no_rows")
    if rolling.empty:
        warnings.append("rolling_stability_unavailable:no_rows")
    return StrengthMappingResult(
        degraded_data=degraded.sort_values(["signal", "label_id", "scenario"]).reset_index(drop=True)
        if not degraded.empty
        else degraded,
        regime_results=regime_results.sort_values(["signal", "label_id", "regime"]).reset_index(drop=True)
        if not regime_results.empty
        else regime_results,
        rolling_stability=rolling.sort_values(["signal", "label_id", "window_start"]).reset_index(drop=True)
        if not rolling.empty
        else rolling,
        by_label=enriched.sort_values(["signal", "label_id"]).reset_index(drop=True),
        config={
            "enabled": True,
            "degraded_scenarios": scenarios,
            "rolling_window_months": int(rolling_window),
            "regime_method": "expanding_monthly_return_drawdown_volatility_v1",
        },
        warnings=warnings,
    )
