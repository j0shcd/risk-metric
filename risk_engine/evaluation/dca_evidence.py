from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

import numpy as np
import pandas as pd

from risk_engine.cycle_model import _ledger_period_return

from .config import EvaluationConfig
from .practical import _max_drawdown, _xirr
from .walkforward import _month_end_series


MIN_ROLLING_WINDOW_MONTHS = 48
ACCUMULATION_DEPLOYMENT_DEADLINE_MONTHS = 48
ANNUAL_CASH_YIELD = 0.03
SIGNAL_HORIZONS_MONTHS = (48,)
PRICE_VALUATION_LOOKBACK_MONTHS = 48
PRICE_VALUATION_MIN_HISTORY_MONTHS = 24


@dataclass(frozen=True)
class DcaEvidenceResult:
    summary: pd.DataFrame
    accumulation_windows: pd.DataFrame
    policy_attribution_windows: pd.DataFrame
    derisking_windows: pd.DataFrame
    signal_value: pd.DataFrame
    causality_audit: pd.DataFrame


def _causal_percentile(values: pd.Series, min_history: int) -> pd.Series:
    clean = pd.to_numeric(values, errors="coerce")
    out = pd.Series(np.nan, index=clean.index, dtype=float)
    for position, (date, value) in enumerate(clean.items()):
        history = clean.iloc[: position + 1].dropna()
        if not np.isfinite(value) or len(history) < min_history:
            continue
        out.loc[date] = float((history <= float(value)).mean())
    return out


def _price_only_risk(price: pd.Series) -> pd.Series:
    monthly = pd.to_numeric(price, errors="coerce")
    trailing_median = monthly.rolling(
        PRICE_VALUATION_LOOKBACK_MONTHS,
        min_periods=PRICE_VALUATION_MIN_HISTORY_MONTHS,
    ).median()
    valuation = np.log(monthly / trailing_median.replace({0.0: np.nan}))
    return _causal_percentile(valuation, PRICE_VALUATION_MIN_HISTORY_MONTHS).rename("price_only_risk")


def _cash_monthly_rate() -> float:
    return float((1.0 + ANNUAL_CASH_YIELD) ** (1.0 / 12.0) - 1.0)


def _cost_rate(config: EvaluationConfig) -> float:
    return max(
        0.0,
        float(config.cycle_dynamic_dca_fee_rate) + float(config.cycle_dynamic_dca_slippage_rate),
    )


def _region_strength(score: float, *, buy_threshold: float, sell_threshold: float) -> tuple[float, float]:
    if not np.isfinite(score):
        return 0.0, 0.0
    buy_strength = (
        float(np.clip((buy_threshold - score) / max(buy_threshold, 1e-12), 0.0, 1.0))
        if score <= buy_threshold
        else 0.0
    )
    sell_strength = (
        float(np.clip((score - sell_threshold) / max(1.0 - sell_threshold, 1e-12), 0.0, 1.0))
        if score >= sell_threshold
        else 0.0
    )
    return buy_strength, sell_strength


def _accumulation_ledger(
    price: pd.Series,
    applied_score: pd.Series,
    *,
    strategy: str,
    config: EvaluationConfig,
) -> pd.DataFrame:
    cost_rate = _cost_rate(config)
    buy_threshold = 1.0 - float(config.cycle_dynamic_dca_buy_threshold)
    max_multiplier = max(1.0, float(config.cycle_dynamic_dca_max_buy_multiplier))
    contribution = max(float(config.cycle_dynamic_dca_base_contribution), 0.0)
    cash = 0.0
    units = 0.0
    previous_equity = 0.0
    twr_equity = 1.0
    rows: List[Dict[str, Any]] = []

    for position, (date, px) in enumerate(pd.to_numeric(price, errors="coerce").dropna().items()):
        if px <= 0.0:
            continue
        pre_flow_equity = cash + units * float(px)
        cash *= 1.0 + _cash_monthly_rate()
        cash += contribution
        score = float(applied_score.get(date, np.nan))
        buy_strength, sell_strength = _region_strength(
            score,
            buy_threshold=buy_threshold,
            sell_threshold=float(config.cycle_dynamic_dca_sell_threshold),
        )

        fixed_buys = strategy in {"fixed_dca", "fixed_buys_risk_sells"}
        risk_buys = strategy in {"risk_accumulation", "risk_buys_and_sells"}
        risk_sells = strategy in {"fixed_buys_risk_sells", "risk_buys_and_sells"}
        if fixed_buys:
            desired_buy = contribution
        else:
            opportunity_buy = contribution * (1.0 + buy_strength * (max_multiplier - 1.0)) if buy_strength > 0 else 0.0
            forced_buy = contribution if position >= ACCUMULATION_DEPLOYMENT_DEADLINE_MONTHS else 0.0
            desired_buy = max(opportunity_buy, forced_buy)
        planned_buy = min(max(desired_buy, 0.0), cash)
        planned_sell = units * float(px) * float(config.cycle_dynamic_dca_max_sell_fraction) * sell_strength if risk_sells else 0.0
        net_trade = planned_buy - planned_sell
        buy_usd = max(net_trade, 0.0)
        sell_usd = max(-net_trade, 0.0)
        if buy_usd > 0.0:
            fee = buy_usd * cost_rate
            units += max(buy_usd - fee, 0.0) / float(px)
            cash -= buy_usd
        elif sell_usd > 0.0:
            units -= sell_usd / float(px)
            cash += sell_usd * (1.0 - cost_rate)
        equity = cash + units * float(px)
        twr_return = _ledger_period_return(previous_equity, pre_flow_equity, contribution, equity)
        twr_equity *= 1.0 + twr_return
        previous_equity = equity
        rows.append(
            {
                "date": date,
                "strategy": strategy,
                "price": float(px),
                "score_used": score,
                "contribution": contribution,
                "buy_usd": buy_usd,
                "sell_usd": sell_usd,
                "cash": cash,
                "units": units,
                "equity": equity,
                "twr_equity": twr_equity,
            }
        )
    return pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame()


def _accumulation_summary(ledger: pd.DataFrame) -> Dict[str, Any]:
    if ledger.empty:
        return {}
    contributions = pd.Series(
        ledger["contribution"].to_numpy(dtype=float),
        index=pd.to_datetime(ledger.index),
    )
    terminal = float(ledger["equity"].iloc[-1])
    return {
        "months": int(len(ledger)),
        "terminal_wealth": terminal,
        "btc_units": float(ledger["units"].iloc[-1]),
        "ending_cash": float(ledger["cash"].iloc[-1]),
        "total_bought": float(pd.to_numeric(ledger["buy_usd"], errors="coerce").fillna(0.0).sum()),
        "total_sold": float(pd.to_numeric(ledger["sell_usd"], errors="coerce").fillna(0.0).sum()),
        "money_weighted_return": _xirr(contributions, terminal),
        "max_drawdown": _max_drawdown(ledger["twr_equity"]),
        "total_contributed": float(contributions.sum()),
    }


def _derisking_ledger(
    price: pd.Series,
    applied_score: pd.Series,
    *,
    strategy: str,
    config: EvaluationConfig,
) -> pd.DataFrame:
    cost_rate = _cost_rate(config)
    buy_threshold = 1.0 - float(config.cycle_dynamic_dca_buy_threshold)
    sell_threshold = float(config.cycle_dynamic_dca_sell_threshold)
    trade_fraction = float(np.clip(config.cycle_dynamic_dca_max_sell_fraction, 0.0, 1.0))
    units = 1.0
    cash = 0.0
    rows: List[Dict[str, Any]] = []

    for date, px in pd.to_numeric(price, errors="coerce").dropna().items():
        if px <= 0.0:
            continue
        cash *= 1.0 + _cash_monthly_rate()
        score = float(applied_score.get(date, np.nan))
        buy_strength, sell_strength = _region_strength(
            score,
            buy_threshold=buy_threshold,
            sell_threshold=sell_threshold,
        )
        buy_usd = 0.0
        sell_usd = 0.0
        if strategy != "hold" and sell_strength > 0.0 and units > 0.0:
            sell_usd = units * float(px) * trade_fraction * sell_strength
            units -= sell_usd / float(px)
            cash += sell_usd * (1.0 - cost_rate)
        elif strategy != "hold" and buy_strength > 0.0 and cash > 0.0:
            buy_usd = cash * trade_fraction * buy_strength
            units += buy_usd * (1.0 - cost_rate) / float(px)
            cash -= buy_usd
        rows.append(
            {
                "date": date,
                "strategy": strategy,
                "price": float(px),
                "score_used": score,
                "buy_usd": buy_usd,
                "sell_usd": sell_usd,
                "cash": cash,
                "units": units,
                "equity": cash + units * float(px),
            }
        )
    return pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame()


def _derisking_summary(ledger: pd.DataFrame, hold: pd.DataFrame) -> Dict[str, Any]:
    if ledger.empty or hold.empty:
        return {}
    equity = pd.to_numeric(ledger["equity"], errors="coerce")
    hold_equity = pd.to_numeric(hold["equity"], errors="coerce")
    returns = equity.pct_change(fill_method=None).fillna(0.0)
    hold_returns = hold_equity.pct_change(fill_method=None).fillna(0.0)
    years = max((len(equity) - 1) / 12.0, 1.0 / 12.0)
    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0)
    hold_total_return = float(hold_equity.iloc[-1] / hold_equity.iloc[0] - 1.0)
    max_drawdown = _max_drawdown(equity)
    hold_drawdown = _max_drawdown(hold_equity)
    drawdown_reduction = abs(hold_drawdown) - abs(max_drawdown)
    positive_hold = hold_returns > 0.0
    negative_hold = hold_returns < 0.0
    upside_capture = (
        float(returns.loc[positive_hold].sum() / hold_returns.loc[positive_hold].sum())
        if positive_hold.any() and hold_returns.loc[positive_hold].sum() != 0.0
        else np.nan
    )
    downside_capture = (
        float(returns.loc[negative_hold].sum() / hold_returns.loc[negative_hold].sum())
        if negative_hold.any() and hold_returns.loc[negative_hold].sum() != 0.0
        else np.nan
    )
    cagr = float((equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0)
    calmar = cagr / abs(max_drawdown) if max_drawdown < 0.0 else np.nan
    hold_cagr = float((hold_equity.iloc[-1] / hold_equity.iloc[0]) ** (1.0 / years) - 1.0)
    hold_calmar = hold_cagr / abs(hold_drawdown) if hold_drawdown < 0.0 else np.nan
    return {
        "months": int(len(equity)),
        "terminal_wealth": float(equity.iloc[-1]),
        "total_return": total_return,
        "max_drawdown": max_drawdown,
        "drawdown_reduction_vs_hold": drawdown_reduction,
        "upside_capture": upside_capture,
        "downside_capture": downside_capture,
        "calmar": calmar,
        "calmar_delta_vs_hold": calmar - hold_calmar if np.isfinite(calmar) and np.isfinite(hold_calmar) else np.nan,
        "terminal_wealth_delta_vs_hold": float(equity.iloc[-1] - hold_equity.iloc[-1]),
        "terminal_wealth_delta_pct_vs_hold": float(equity.iloc[-1] / hold_equity.iloc[-1] - 1.0),
        "return_lost_per_drawdown_avoided": (
            max(hold_total_return - total_return, 0.0) / drawdown_reduction
            if drawdown_reduction > 1e-12
            else np.nan
        ),
    }


def _forward_outcomes(price: pd.Series, horizon: int) -> pd.DataFrame:
    values = pd.to_numeric(price, errors="coerce")
    rows: List[Dict[str, Any]] = []
    for position in range(0, max(0, len(values) - horizon)):
        start = float(values.iloc[position])
        future = values.iloc[position + 1 : position + horizon + 1].dropna()
        if not np.isfinite(start) or start <= 0.0 or len(future) < horizon:
            continue
        rows.append(
            {
                "date": values.index[position],
                "forward_return": float(future.iloc[-1] / start - 1.0),
                "forward_max_drawdown": float(future.min() / start - 1.0),
                "forward_max_rally": float(future.max() / start - 1.0),
            }
        )
    return pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame()


def _risk_region(score: pd.Series, config: EvaluationConfig) -> pd.Series:
    buy_threshold = 1.0 - float(config.cycle_dynamic_dca_buy_threshold)
    sell_threshold = float(config.cycle_dynamic_dca_sell_threshold)
    clean = pd.to_numeric(score, errors="coerce")
    region = pd.Series("mid", index=clean.index, dtype=object)
    region.loc[clean <= buy_threshold] = "low"
    region.loc[clean >= sell_threshold] = "high"
    return region.where(clean.notna())


def _shift_candidates(length: int, smoke_mode: bool) -> List[int]:
    candidates = list(range(12, max(12, length - 11)))
    if smoke_mode and len(candidates) > 31:
        positions = np.linspace(0, len(candidates) - 1, 31).round().astype(int)
        return [candidates[position] for position in sorted(set(positions))]
    return candidates


def _signal_spreads(frame: pd.DataFrame) -> tuple[float, float, float]:
    grouped = frame.groupby("region", observed=True)
    medians = grouped[["forward_return", "forward_max_drawdown", "forward_max_rally"]].median()
    if not {"low", "high"}.issubset(medians.index):
        return np.nan, np.nan, np.nan
    return (
        float(medians.loc["low", "forward_return"] - medians.loc["high", "forward_return"]),
        float(medians.loc["low", "forward_max_drawdown"] - medians.loc["high", "forward_max_drawdown"]),
        float(medians.loc["low", "forward_max_rally"] - medians.loc["high", "forward_max_rally"]),
    )


def _signal_value_rows(
    price: pd.Series,
    scores: Dict[str, pd.Series],
    config: EvaluationConfig,
) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    shifts = _shift_candidates(len(price), config.smoke_mode)
    for horizon in SIGNAL_HORIZONS_MONTHS:
        outcomes = _forward_outcomes(price, horizon)
        for signal_name, score in scores.items():
            aligned_score = pd.to_numeric(score, errors="coerce").reindex(outcomes.index)
            frame = outcomes.copy()
            frame["score"] = aligned_score
            frame["region"] = _risk_region(aligned_score, config)
            frame = frame.dropna(subset=["score", "region"])
            return_spread, drawdown_spread, rally_spread = _signal_spreads(frame)
            null_return: List[float] = []
            null_drawdown: List[float] = []
            score_values = aligned_score.to_numpy(dtype=float)
            for shift in shifts:
                shifted = pd.Series(np.roll(score_values, shift), index=outcomes.index)
                placebo = outcomes.copy()
                placebo["region"] = _risk_region(shifted, config)
                placebo = placebo.dropna(subset=["region"])
                null_ret, null_dd, _ = _signal_spreads(placebo)
                if np.isfinite(null_ret):
                    null_return.append(null_ret)
                if np.isfinite(null_dd):
                    null_drawdown.append(null_dd)
            return_p = (
                float((1 + sum(value >= return_spread for value in null_return)) / (1 + len(null_return)))
                if np.isfinite(return_spread) and null_return
                else np.nan
            )
            drawdown_p = (
                float((1 + sum(value >= drawdown_spread for value in null_drawdown)) / (1 + len(null_drawdown)))
                if np.isfinite(drawdown_spread) and null_drawdown
                else np.nan
            )
            counts = frame["region"].value_counts()
            rows.append(
                {
                    "signal": signal_name,
                    "horizon_months": horizon,
                    "observations": int(len(frame)),
                    "effective_observations": int(len(frame) // horizon),
                    "low_region_observations": int(counts.get("low", 0)),
                    "mid_region_observations": int(counts.get("mid", 0)),
                    "high_region_observations": int(counts.get("high", 0)),
                    "low_minus_high_forward_return": return_spread,
                    "low_minus_high_forward_drawdown": drawdown_spread,
                    "low_minus_high_forward_rally": rally_spread,
                    "return_spread_placebo_p_right": return_p,
                    "drawdown_spread_placebo_p_right": drawdown_p,
                    "return_order_is_useful": bool(np.isfinite(return_spread) and return_spread > 0.0),
                    "drawdown_order_is_useful": bool(np.isfinite(drawdown_spread) and drawdown_spread > 0.0),
                }
            )
    return pd.DataFrame(rows)


def _finite_median(values: pd.Series) -> float:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    return float(clean.median()) if not clean.empty else np.nan


def _relative_window_rows(
    available: pd.DataFrame,
    config: EvaluationConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, pd.DataFrame]]:
    accumulation_rows: List[Dict[str, Any]] = []
    attribution_rows: List[Dict[str, Any]] = []
    derisking_rows: List[Dict[str, Any]] = []
    full_ledgers: Dict[str, pd.DataFrame] = {}
    final_start = len(available) - MIN_ROLLING_WINDOW_MONTHS
    for start_position in range(final_start + 1):
        window = available.iloc[start_position:]
        applied_scores = {
            "risk_accumulation": window["dca_risk_applied"],
            "price_only_accumulation": window["price_only_risk_applied"],
        }
        accumulation_ledgers = {
            "fixed_dca": _accumulation_ledger(
                window["price"], pd.Series(np.nan, index=window.index), strategy="fixed_dca", config=config
            )
        }
        for strategy, score in applied_scores.items():
            accumulation_ledgers[strategy] = _accumulation_ledger(
                window["price"], score, strategy=strategy, config=config
            )
        accumulation_summaries = {
            strategy: _accumulation_summary(ledger) for strategy, ledger in accumulation_ledgers.items()
        }
        fixed = accumulation_summaries["fixed_dca"]
        for strategy, summary in accumulation_summaries.items():
            accumulation_rows.append(
                {
                    "start_date": window.index[0],
                    "end_date": window.index[-1],
                    "strategy": strategy,
                    **summary,
                    "terminal_wealth_delta_vs_fixed": float(summary["terminal_wealth"] - fixed["terminal_wealth"]),
                    "terminal_wealth_delta_pct_vs_fixed": float(summary["terminal_wealth"] / fixed["terminal_wealth"] - 1.0),
                    "btc_units_delta_vs_fixed": float(summary["btc_units"] - fixed["btc_units"]),
                    "beats_fixed": bool(summary["terminal_wealth"] > fixed["terminal_wealth"]),
                    "same_external_cashflows": bool(np.isclose(summary["total_contributed"], fixed["total_contributed"])),
                    "sales_allowed": False,
                    "deployment_deadline_months": ACCUMULATION_DEPLOYMENT_DEADLINE_MONTHS,
                }
            )

        attribution_ledgers = {
            "fixed_dca": accumulation_ledgers["fixed_dca"],
            "risk_buys_only": accumulation_ledgers["risk_accumulation"],
            "fixed_buys_risk_sells": _accumulation_ledger(
                window["price"], window["dca_risk_applied"], strategy="fixed_buys_risk_sells", config=config
            ),
            "risk_buys_and_sells": _accumulation_ledger(
                window["price"], window["dca_risk_applied"], strategy="risk_buys_and_sells", config=config
            ),
        }
        attribution_summaries = {
            strategy: _accumulation_summary(ledger) for strategy, ledger in attribution_ledgers.items()
        }
        attribution_fixed = attribution_summaries["fixed_dca"]
        for strategy, summary in attribution_summaries.items():
            attribution_rows.append(
                {
                    "start_date": window.index[0],
                    "end_date": window.index[-1],
                    "strategy": strategy,
                    **summary,
                    "terminal_wealth_delta_pct_vs_fixed": float(
                        summary["terminal_wealth"] / attribution_fixed["terminal_wealth"] - 1.0
                    ),
                    "same_external_cashflows": bool(
                        np.isclose(summary["total_contributed"], attribution_fixed["total_contributed"])
                    ),
                }
            )

        hold = _derisking_ledger(
            window["price"], pd.Series(np.nan, index=window.index), strategy="hold", config=config
        )
        derisk_ledgers = {
            "hold": hold,
            "risk_derisking": _derisking_ledger(
                window["price"], window["dca_risk_applied"], strategy="risk_derisking", config=config
            ),
            "price_only_derisking": _derisking_ledger(
                window["price"], window["price_only_risk_applied"], strategy="price_only_derisking", config=config
            ),
        }
        for strategy, ledger in derisk_ledgers.items():
            derisking_rows.append(
                {
                    "start_date": window.index[0],
                    "end_date": window.index[-1],
                    "strategy": strategy,
                    "initial_btc_units": 1.0,
                    "external_contributions": 0.0,
                    **_derisking_summary(ledger, hold),
                }
            )
        if start_position == 0:
            for strategy, ledger in {**accumulation_ledgers, **attribution_ledgers, **derisk_ledgers}.items():
                full_ledgers[strategy] = ledger
    return (
        pd.DataFrame(accumulation_rows),
        pd.DataFrame(attribution_rows),
        pd.DataFrame(derisking_rows),
        full_ledgers,
    )


def _summary_rows(
    accumulation: pd.DataFrame,
    attribution: pd.DataFrame,
    derisking: pd.DataFrame,
    signal_value: pd.DataFrame,
) -> pd.DataFrame:
    risk_accum = accumulation.loc[accumulation["strategy"].eq("risk_accumulation")]
    price_accum = accumulation.loc[accumulation["strategy"].eq("price_only_accumulation")]
    risk_derisk = derisking.loc[derisking["strategy"].eq("risk_derisking")]
    price_derisk = derisking.loc[derisking["strategy"].eq("price_only_derisking")]
    dca_signal = signal_value.loc[signal_value["signal"].eq("dca_risk")]
    price_signal = signal_value.loc[signal_value["signal"].eq("price_only_risk")]
    attribution_medians = (
        attribution.groupby("strategy", observed=True)["terminal_wealth_delta_pct_vs_fixed"].median()
        if not attribution.empty
        else pd.Series(dtype=float)
    )

    accumulation_supported = bool(
        not risk_accum.empty
        and float(risk_accum["beats_fixed"].mean()) > 0.50
        and _finite_median(risk_accum["terminal_wealth_delta_pct_vs_fixed"]) > 0.0
        and _finite_median(risk_accum["terminal_wealth"]) > _finite_median(price_accum["terminal_wealth"])
    )
    derisk_supported = bool(
        not risk_derisk.empty
        and _finite_median(risk_derisk["calmar_delta_vs_hold"]) > 0.0
        and float((risk_derisk["calmar_delta_vs_hold"] > 0.0).mean()) > 0.50
        and _finite_median(risk_derisk["calmar"]) > _finite_median(price_derisk["calmar"])
    )
    signal_supported = bool(
        len(dca_signal) == len(SIGNAL_HORIZONS_MONTHS)
        and dca_signal["return_order_is_useful"].astype(bool).all()
        and dca_signal["drawdown_order_is_useful"].astype(bool).all()
        and (pd.to_numeric(dca_signal["return_spread_placebo_p_right"], errors="coerce") <= 0.10).all()
        and _finite_median(dca_signal["low_minus_high_forward_return"])
        > _finite_median(price_signal["low_minus_high_forward_return"])
    )
    return pd.DataFrame(
        [
            {
                "test": "accumulation_only",
                "status": "pass" if accumulation_supported else "fail",
                "windows": int(risk_accum.shape[0]),
                "win_rate_vs_fixed": float(risk_accum["beats_fixed"].mean()),
                "median_terminal_wealth_delta_pct_vs_fixed": float(
                    _finite_median(risk_accum["terminal_wealth_delta_pct_vs_fixed"])
                ),
                "median_btc_units_delta_vs_fixed": _finite_median(risk_accum["btc_units_delta_vs_fixed"]),
                "median_terminal_wealth_delta_vs_price_only": float(
                    _finite_median(risk_accum["terminal_wealth"])
                    - _finite_median(price_accum["terminal_wealth"])
                ),
                "cash_yield_annual": ANNUAL_CASH_YIELD,
                "deployment_deadline_months": ACCUMULATION_DEPLOYMENT_DEADLINE_MONTHS,
            },
            {
                "test": "derisking",
                "status": "pass" if derisk_supported else "fail",
                "windows": int(risk_derisk.shape[0]),
                "terminal_wealth_win_rate_vs_hold": float(
                    (risk_derisk["terminal_wealth_delta_vs_hold"] > 0.0).mean()
                ),
                "calmar_win_rate_vs_hold": float((risk_derisk["calmar_delta_vs_hold"] > 0.0).mean()),
                "median_terminal_wealth_delta_vs_hold": _finite_median(risk_derisk["terminal_wealth_delta_vs_hold"]),
                "median_terminal_wealth_delta_pct_vs_hold": _finite_median(
                    risk_derisk["terminal_wealth_delta_pct_vs_hold"]
                ),
                "median_terminal_wealth_delta_pct_vs_price_only": _finite_median(
                    risk_derisk["terminal_wealth"].reset_index(drop=True)
                    / price_derisk["terminal_wealth"].reset_index(drop=True)
                    - 1.0
                ),
                "median_drawdown_reduction_vs_hold": _finite_median(risk_derisk["drawdown_reduction_vs_hold"]),
                "median_calmar_delta_vs_hold": _finite_median(risk_derisk["calmar_delta_vs_hold"]),
                "median_calmar_delta_vs_price_only": float(
                    _finite_median(risk_derisk["calmar"]) - _finite_median(price_derisk["calmar"])
                ),
                "median_cashflow_delta_fixed_buys_risk_sells": float(
                    attribution_medians.get("fixed_buys_risk_sells", np.nan)
                ),
                "median_cashflow_delta_risk_buys_only": float(
                    attribution_medians.get("risk_buys_only", np.nan)
                ),
                "median_cashflow_delta_risk_buys_and_sells": float(
                    attribution_medians.get("risk_buys_and_sells", np.nan)
                ),
            },
            {
                "test": "signal_value",
                "status": "pass" if signal_supported else "fail",
                "horizons": int(dca_signal.shape[0]),
                "median_low_minus_high_forward_return": float(
                    _finite_median(dca_signal["low_minus_high_forward_return"])
                ),
                "median_low_minus_high_forward_drawdown": float(
                    _finite_median(dca_signal["low_minus_high_forward_drawdown"])
                ),
                "worst_return_spread_placebo_p_right": float(
                    dca_signal["return_spread_placebo_p_right"].max()
                ),
                "median_return_spread_advantage_vs_price_only": float(
                    _finite_median(dca_signal["low_minus_high_forward_return"])
                    - _finite_median(price_signal["low_minus_high_forward_return"])
                ),
            },
        ]
    )


def _causality_audit(
    available: pd.DataFrame,
    full_ledgers: Dict[str, pd.DataFrame],
    config: EvaluationConfig,
) -> pd.DataFrame:
    cutoff_position = len(available) * 2 // 3
    cutoff = available.index[cutoff_position]
    mutated_score = available["dca_risk_applied"].copy()
    mutated_score.loc[mutated_score.index > cutoff] = 1.0 - mutated_score.loc[mutated_score.index > cutoff]
    mutated_accum = _accumulation_ledger(
        available["price"], mutated_score, strategy="risk_accumulation", config=config
    )
    mutated_derisk = _derisking_ledger(
        available["price"], mutated_score, strategy="risk_derisking", config=config
    )
    mutated_fixed_buys_risk_sells = _accumulation_ledger(
        available["price"], mutated_score, strategy="fixed_buys_risk_sells", config=config
    )
    mutated_risk_buys_and_sells = _accumulation_ledger(
        available["price"], mutated_score, strategy="risk_buys_and_sells", config=config
    )
    mutated_price = available["price"].copy()
    mutated_price.loc[mutated_price.index > cutoff] *= 10.0
    baseline_price_risk = _price_only_risk(available["price"])
    recomputed_price_risk = _price_only_risk(mutated_price)
    price_score_prefix_unchanged = bool(
        np.allclose(
            baseline_price_risk.loc[baseline_price_risk.index <= cutoff].to_numpy(dtype=float),
            recomputed_price_risk.loc[recomputed_price_risk.index <= cutoff].to_numpy(dtype=float),
            equal_nan=True,
        )
    )

    def unchanged(left: pd.DataFrame, right: pd.DataFrame, columns: Iterable[str]) -> bool:
        left_prefix = left.loc[left.index <= cutoff, list(columns)]
        right_prefix = right.loc[right.index <= cutoff, list(columns)]
        return bool(
            left_prefix.index.equals(right_prefix.index)
            and np.allclose(
                left_prefix.to_numpy(dtype=float),
                right_prefix.to_numpy(dtype=float),
                equal_nan=True,
            )
        )

    accumulation_prefix_unchanged = unchanged(
        full_ledgers["risk_accumulation"], mutated_accum, ["cash", "units", "equity", "buy_usd", "score_used"]
    )
    derisking_prefix_unchanged = unchanged(
        full_ledgers["risk_derisking"], mutated_derisk, ["cash", "units", "equity", "buy_usd", "sell_usd", "score_used"]
    )
    exit_only_prefix_unchanged = unchanged(
        full_ledgers["fixed_buys_risk_sells"],
        mutated_fixed_buys_risk_sells,
        ["cash", "units", "equity", "buy_usd", "sell_usd", "score_used"],
    )
    combined_prefix_unchanged = unchanged(
        full_ledgers["risk_buys_and_sells"],
        mutated_risk_buys_and_sells,
        ["cash", "units", "equity", "buy_usd", "sell_usd", "score_used"],
    )
    first_execution_is_lagged = bool(pd.isna(available["dca_risk_applied"].iloc[0]))
    prior_month_signal_matches = bool(
        np.allclose(
            available["dca_risk_applied"].iloc[1:].to_numpy(dtype=float),
            available["dca_risk"].iloc[:-1].to_numpy(dtype=float),
            equal_nan=True,
        )
    )
    return pd.DataFrame(
        [
            {
                "cutoff_date": cutoff,
                "future_suffix_mutated": True,
                "accumulation_prefix_unchanged": accumulation_prefix_unchanged,
                "derisking_prefix_unchanged": derisking_prefix_unchanged,
                "exit_only_prefix_unchanged": exit_only_prefix_unchanged,
                "combined_policy_prefix_unchanged": combined_prefix_unchanged,
                "price_only_score_prefix_unchanged": price_score_prefix_unchanged,
                "first_execution_has_no_contemporaneous_signal": first_execution_is_lagged,
                "execution_uses_prior_month_dca_risk": prior_month_signal_matches,
                "passes_causality_audit": accumulation_prefix_unchanged
                and derisking_prefix_unchanged
                and exit_only_prefix_unchanged
                and combined_prefix_unchanged
                and price_score_prefix_unchanged
                and first_execution_is_lagged
                and prior_month_signal_matches,
            }
        ]
    )


def evaluate_dca_evidence(
    series: pd.DataFrame,
    walkforward_by_label: pd.DataFrame,
    config: EvaluationConfig,
) -> DcaEvidenceResult:
    del walkforward_by_label  # The compact suite now evaluates the three decision problems directly.
    required = {"btc_price", "dca_risk"}
    if not required.issubset(series.columns):
        empty = pd.DataFrame()
        return DcaEvidenceResult(empty, empty, empty, empty, empty, empty)

    price = _month_end_series(series["btc_price"])
    dca_risk = _month_end_series(series["dca_risk"]).reindex(price.index)
    price_only_risk = _price_only_risk(price)
    frame = pd.DataFrame(
        {
            "price": price,
            "dca_risk": dca_risk,
            "price_only_risk": price_only_risk,
            "dca_risk_applied": dca_risk.shift(1),
            "price_only_risk_applied": price_only_risk.shift(1),
        }
    ).dropna(subset=["price", "dca_risk"])
    if len(frame) < MIN_ROLLING_WINDOW_MONTHS:
        empty = pd.DataFrame()
        return DcaEvidenceResult(empty, empty, empty, empty, empty, empty)

    accumulation, attribution, derisking, full_ledgers = _relative_window_rows(frame, config)
    signal_value = _signal_value_rows(
        frame["price"],
        {"dca_risk": frame["dca_risk"], "price_only_risk": frame["price_only_risk"]},
        config,
    )
    summary = _summary_rows(accumulation, attribution, derisking, signal_value)
    causality = _causality_audit(frame, full_ledgers, config)
    return DcaEvidenceResult(summary, accumulation, attribution, derisking, signal_value, causality)
