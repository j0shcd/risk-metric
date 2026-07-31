from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from .config import EvaluationConfig
from .walkforward import _month_end_series


@dataclass(frozen=True)
class PracticalStrategyResult:
    results: pd.DataFrame
    curves: pd.DataFrame
    trades: pd.DataFrame
    config: Dict[str, Any]
    warnings: List[str]


PRODUCTION_DCA_POLICY_FAMILY = "production_dca_cashflow"


def _stable_int(value: str) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def _max_drawdown(equity: pd.Series) -> float:
    clean = pd.to_numeric(equity, errors="coerce").dropna()
    if clean.empty:
        return float("nan")
    peak = clean.cummax()
    drawdown = clean / peak.replace({0.0: np.nan}) - 1.0
    return float(drawdown.min())


def _cagr(equity: pd.Series, periods_per_year: float = 12.0) -> float:
    clean = pd.to_numeric(equity, errors="coerce").dropna()
    if clean.shape[0] < 2:
        return float("nan")
    terminal = float(clean.iloc[-1])
    if terminal <= 0.0:
        return -1.0
    years = max((clean.shape[0] - 1) / max(float(periods_per_year), 1e-9), 1.0 / max(float(periods_per_year), 1e-9))
    return float(terminal ** (1.0 / years) - 1.0)


def _xirr(contributions: pd.Series, terminal_value: float) -> float:
    flows = pd.to_numeric(contributions, errors="coerce").fillna(0.0).mul(-1.0)
    if flows.empty or not np.isfinite(terminal_value):
        return float("nan")
    flows.iloc[-1] += float(terminal_value)
    if not (bool((flows < 0.0).any()) and bool((flows > 0.0).any())):
        return float("nan")
    dates = pd.to_datetime(flows.index)
    years = (dates - dates[0]).days.astype(float) / 365.2425

    def npv(rate: float) -> float:
        return float(np.sum(flows.to_numpy() / np.power(1.0 + rate, years)))

    low, high = -0.9999, 1.0
    low_value, high_value = npv(low), npv(high)
    while np.sign(low_value) == np.sign(high_value) and high < 1_000_000.0:
        high *= 2.0
        high_value = npv(high)
    if np.sign(low_value) == np.sign(high_value):
        return float("nan")
    for _ in range(160):
        mid = (low + high) / 2.0
        mid_value = npv(mid)
        if abs(mid_value) <= 1e-10:
            return float(mid)
        if np.sign(mid_value) == np.sign(low_value):
            low, low_value = mid, mid_value
        else:
            high = mid
    return float((low + high) / 2.0)


def _direction(signal: str) -> str:
    lowered = str(signal).lower()
    if "bottom" in lowered or "accumulation" in lowered or "buy" in lowered:
        return "high_score_more_exposure"
    return "low_score_more_exposure"


def _score_to_exposure(score: pd.Series, direction: str, mode: str) -> pd.Series:
    clean = pd.to_numeric(score, errors="coerce").clip(0.0, 1.0)
    favorable = clean if direction == "high_score_more_exposure" else 1.0 - clean
    if mode == "bands":
        exposure = pd.Series(0.50, index=clean.index, dtype=float)
        exposure.loc[favorable >= 0.75] = 1.00
        exposure.loc[(favorable >= 0.55) & (favorable < 0.75)] = 0.75
        exposure.loc[(favorable >= 0.35) & (favorable < 0.55)] = 0.50
        exposure.loc[(favorable >= 0.20) & (favorable < 0.35)] = 0.25
        exposure.loc[favorable < 0.20] = 0.00
        return exposure
    if mode == "conservative":
        return (0.20 + 0.60 * favorable).clip(0.0, 0.80)
    return favorable.clip(0.0, 1.0)


def _hysteresis(exposure: pd.Series, threshold: float = 0.20) -> pd.Series:
    out = pd.Series(index=exposure.index, dtype=float)
    current = 0.50
    for date, value in exposure.items():
        if not np.isfinite(value):
            out.loc[date] = current
            continue
        if abs(float(value) - current) >= threshold:
            current = float(value)
        out.loc[date] = current
    return out


def _simulate_allocation(
    price: pd.Series,
    target_exposure: pd.Series,
    *,
    cost_bps: float,
    strategy: str,
    signal: str,
) -> tuple[Dict[str, Any], pd.DataFrame, pd.DataFrame]:
    monthly_price = _month_end_series(price)
    returns = monthly_price.pct_change(fill_method=None).fillna(0.0)
    target = pd.to_numeric(target_exposure, errors="coerce").reindex(monthly_price.index).ffill().fillna(0.0).clip(0.0, 1.0)
    applied = target.shift(1).fillna(0.0)
    turnover = applied.diff().abs().fillna(applied.abs())
    cost_rate = float(cost_bps) / 10000.0
    strategy_returns = applied * returns - turnover * cost_rate
    equity = (1.0 + strategy_returns).cumprod()
    if equity.empty:
        summary = {
            "signal": signal,
            "strategy": strategy,
            "cost_bps": float(cost_bps),
            "months": 0,
            "total_return": np.nan,
            "cagr": np.nan,
            "max_drawdown": np.nan,
            "volatility": np.nan,
            "sharpe": np.nan,
            "calmar": np.nan,
            "turnover_per_year": np.nan,
            "avg_exposure": np.nan,
            "cost_drag": np.nan,
        }
        return summary, pd.DataFrame(), pd.DataFrame()

    cagr = _cagr(equity)
    mdd = _max_drawdown(equity)
    vol = float(strategy_returns.std(ddof=0) * np.sqrt(12.0)) if len(strategy_returns) else np.nan
    mean_return = float(strategy_returns.mean() * 12.0) if len(strategy_returns) else np.nan
    sharpe = float(mean_return / vol) if np.isfinite(mean_return) and np.isfinite(vol) and vol > 0 else np.nan
    turnover_per_year = float(turnover.mean() * 12.0) if len(turnover) else np.nan
    cost_drag = float((turnover * cost_rate).sum())
    cost_drag_per_year = float(turnover.mean() * 12.0 * cost_rate) if len(turnover) else np.nan
    summary = {
        "signal": signal,
        "strategy": strategy,
        "cost_bps": float(cost_bps),
        "months": int(equity.shape[0]),
        "total_return": float(equity.iloc[-1] - 1.0),
        "cagr": cagr,
        "max_drawdown": mdd,
        "volatility": vol,
        "sharpe": sharpe,
        "calmar": float(cagr / abs(mdd)) if np.isfinite(cagr) and np.isfinite(mdd) and mdd < 0 else np.nan,
        "turnover_per_year": turnover_per_year,
        "avg_exposure": float(applied.mean()),
        "cagr_per_avg_exposure": float(cagr / max(float(applied.mean()), 1e-9)) if np.isfinite(cagr) else np.nan,
        "cost_drag": cost_drag,
        "cost_drag_per_year": cost_drag_per_year,
        "execution_lag": "target_from_month_close_applied_next_month",
    }
    curve = pd.DataFrame(
        {
            "date": monthly_price.index,
            "signal": signal,
            "strategy": strategy,
            "cost_bps": float(cost_bps),
            "price": monthly_price.to_numpy(dtype=float),
            "target_exposure": target.to_numpy(dtype=float),
            "applied_exposure": applied.to_numpy(dtype=float),
            "turnover": turnover.to_numpy(dtype=float),
            "strategy_return": strategy_returns.to_numpy(dtype=float),
            "equity": equity.to_numpy(dtype=float),
        }
    )
    trades = curve.loc[curve["turnover"] > 1e-12, ["date", "signal", "strategy", "cost_bps", "target_exposure", "turnover"]].copy()
    return summary, curve, trades


def _simulate_dca_cashflow(
    price: pd.Series,
    buy_multiplier: pd.Series,
    *,
    cost_bps: float,
    strategy: str,
    signal: str,
) -> tuple[Dict[str, Any], pd.DataFrame, pd.DataFrame]:
    monthly_price = _month_end_series(price)
    multiplier = (
        pd.to_numeric(buy_multiplier, errors="coerce")
        .reindex(monthly_price.index)
        .ffill()
        .fillna(1.0)
        .clip(0.0, 2.0)
    )
    applied_multiplier = multiplier.shift(1).fillna(1.0)
    cost_rate = float(cost_bps) / 10000.0
    base_contribution = 1.0
    cash = 0.0
    units = 0.0
    previous_equity_usd = 0.0
    twr_equity = 1.0
    rows: List[Dict[str, Any]] = []
    trade_rows: List[Dict[str, Any]] = []
    for date, px in monthly_price.items():
        if not np.isfinite(px) or px <= 0.0:
            continue
        pre_contribution_equity = cash + units * float(px)
        cash += base_contribution
        desired_buy = base_contribution * float(applied_multiplier.loc[date])
        buy_usd = min(max(desired_buy, 0.0), cash)
        trade_cost = buy_usd * cost_rate
        net_buy = max(buy_usd - trade_cost, 0.0)
        units += net_buy / float(px)
        cash -= buy_usd
        contributed = base_contribution * (len(rows) + 1)
        equity_usd = cash + units * float(px)
        market_factor = pre_contribution_equity / previous_equity_usd if previous_equity_usd > 0.0 else 1.0
        post_flow_equity = pre_contribution_equity + base_contribution
        trading_factor = equity_usd / post_flow_equity if post_flow_equity > 0.0 else 1.0
        twr_return = float(market_factor * trading_factor - 1.0)
        twr_equity *= 1.0 + twr_return
        previous_equity_usd = equity_usd
        rows.append(
            {
                "date": date,
                "signal": signal,
                "strategy": strategy,
                "cost_bps": float(cost_bps),
                "price": float(px),
                "target_exposure": np.nan,
                "applied_exposure": np.nan,
                "buy_multiplier": float(multiplier.loc[date]),
                "applied_buy_multiplier": float(applied_multiplier.loc[date]),
                "contribution_usd": base_contribution,
                "total_contributed_usd": contributed,
                "buy_usd": buy_usd,
                "cash_usd": cash,
                "btc_units": units,
                "trade_cost_usd": trade_cost,
                "equity_usd": equity_usd,
                "twr_return": twr_return,
                "equity": twr_equity,
            }
        )
        if buy_usd > 1e-12:
            trade_rows.append(
                {
                    "date": date,
                    "signal": signal,
                    "strategy": strategy,
                    "cost_bps": float(cost_bps),
                    "target_exposure": np.nan,
                    "turnover": np.nan,
                    "buy_usd": buy_usd,
                    "trade_cost_usd": trade_cost,
                }
            )

    curve = pd.DataFrame(rows)
    if curve.empty:
        return {}, curve, pd.DataFrame(trade_rows)
    equity = pd.Series(curve["equity"].to_numpy(dtype=float), index=pd.to_datetime(curve["date"]))
    returns = equity.pct_change(fill_method=None).fillna(0.0)
    cagr = _cagr(equity)
    mdd = _max_drawdown(equity)
    vol = float(returns.std(ddof=0) * np.sqrt(12.0)) if len(returns) else np.nan
    mean_return = float(returns.mean() * 12.0) if len(returns) else np.nan
    total_contributed = float(curve["total_contributed_usd"].iloc[-1])
    equity_usd = float(curve["equity_usd"].iloc[-1])
    buy_total = float(curve["buy_usd"].sum())
    cost_total = float(curve["trade_cost_usd"].sum())
    summary = {
        "signal": signal,
        "strategy": strategy,
        "cost_bps": float(cost_bps),
        "months": int(curve.shape[0]),
        "total_return": float(equity.iloc[-1] - 1.0),
        "cagr": cagr,
        "max_drawdown": mdd,
        "volatility": vol,
        "sharpe": float(mean_return / vol) if np.isfinite(mean_return) and np.isfinite(vol) and vol > 0 else np.nan,
        "calmar": float(cagr / abs(mdd)) if np.isfinite(cagr) and np.isfinite(mdd) and mdd < 0 else np.nan,
        "turnover_per_year": float((curve["buy_usd"] / total_contributed).mean() * 12.0) if total_contributed else np.nan,
        "avg_exposure": float((curve["equity_usd"] - curve["cash_usd"]).div(curve["equity_usd"].replace({0.0: np.nan})).mean()),
        "cagr_per_avg_exposure": np.nan,
        "cost_drag": cost_total / max(total_contributed, 1e-9),
        "cost_drag_per_year": float(cost_total / max(total_contributed, 1e-9) / max(curve.shape[0] / 12.0, 1e-9)),
        "execution_lag": "signal_month_close_buy_schedule_applied_next_month",
        "total_contributed_usd": total_contributed,
        "terminal_equity_usd": equity_usd,
        "money_weighted_return": _xirr(
            pd.Series(
                curve["contribution_usd"].to_numpy(dtype=float),
                index=pd.to_datetime(curve["date"]),
            ),
            equity_usd,
        ),
        "gain_on_contributions": equity_usd / total_contributed - 1.0 if total_contributed > 0.0 else np.nan,
        "cash_utilization": float(buy_total / max(total_contributed, 1e-9)),
    }
    return summary, curve, pd.DataFrame(trade_rows)


def _summary_lookup(summary: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    if summary.empty or "strategy" not in summary.columns:
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for _, row in summary.iterrows():
        strategy = str(row.get("strategy", ""))
        if strategy:
            out[strategy] = row.to_dict()
    return out


def _curve_date_index(curves: pd.DataFrame) -> pd.DataFrame:
    if curves.empty:
        return curves.copy()
    frame = curves.copy()
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    elif isinstance(frame.index, pd.DatetimeIndex):
        index_name = frame.index.name or "index"
        frame = frame.reset_index()
        date_column = index_name if index_name in frame.columns else frame.columns[0]
        frame = frame.rename(columns={date_column: "date"})
    else:
        first = frame.columns[0] if len(frame.columns) else None
        if first is not None:
            parsed = pd.to_datetime(frame[first], errors="coerce")
            if parsed.notna().any():
                frame = frame.rename(columns={first: "date"})
                frame["date"] = parsed
    return frame


def evaluate_production_dynamic_dca(
    financial_benchmark_summary: pd.DataFrame,
    financial_benchmark_curves: pd.DataFrame,
) -> PracticalStrategyResult:
    if financial_benchmark_summary.empty:
        return PracticalStrategyResult(
            results=pd.DataFrame(),
            curves=pd.DataFrame(),
            trades=pd.DataFrame(),
            config={"enabled": False},
            warnings=["production_dynamic_dca_unavailable:missing_financial_benchmark_summary"],
        )

    lookup = _summary_lookup(financial_benchmark_summary)
    if not lookup:
        return PracticalStrategyResult(
            results=pd.DataFrame(),
            curves=pd.DataFrame(),
            trades=pd.DataFrame(),
            config={"enabled": False},
            warnings=["production_dynamic_dca_unavailable:missing_strategy_column"],
        )

    fixed = lookup.get("fixed_dca", {})
    buy_hold = lookup.get("buy_and_hold", {})
    curve_frame = _curve_date_index(financial_benchmark_curves)
    dynamic_curve = pd.DataFrame()
    if not curve_frame.empty and "dynamic_dca_equity" in curve_frame.columns:
        dynamic_curve = curve_frame.copy()
    fixed_terminal_value = float(fixed.get("ending_value", np.nan)) if pd.notna(fixed.get("ending_value", np.nan)) else np.nan
    if not np.isfinite(fixed_terminal_value) and "fixed_dca_value" in curve_frame.columns:
        fixed_values = pd.to_numeric(curve_frame["fixed_dca_value"], errors="coerce").dropna()
        fixed_terminal_value = float(fixed_values.iloc[-1]) if not fixed_values.empty else np.nan

    years = np.nan
    if "date" in dynamic_curve.columns:
        dates = pd.to_datetime(dynamic_curve["date"], errors="coerce").dropna()
        if len(dates) >= 2:
            years = max((dates.max() - dates.min()).days / 365.25, 1.0 / 12.0)
    if not np.isfinite(years):
        dynamic_months = len(dynamic_curve) if not dynamic_curve.empty else np.nan
        years = float(dynamic_months) / 12.0 if np.isfinite(dynamic_months) and dynamic_months else np.nan

    trade_cost_total = np.nan
    cost_drag_per_year = 0.0
    turnover_per_year = 0.0
    avg_exposure = np.nan
    terminal_equity_usd = np.nan
    cash_utilization = np.nan
    if not dynamic_curve.empty:
        equity_usd = pd.to_numeric(
            dynamic_curve.get("dynamic_dca_value", dynamic_curve.get("dynamic_dca_equity")),
            errors="coerce",
        )
        terminal_equity_usd = float(equity_usd.dropna().iloc[-1]) if not equity_usd.dropna().empty else np.nan
        buy_usd = pd.to_numeric(dynamic_curve.get("dynamic_dca_buy_usd"), errors="coerce").fillna(0.0)
        sell_usd = pd.to_numeric(dynamic_curve.get("dynamic_dca_sell_usd"), errors="coerce").fillna(0.0)
        trade_costs = pd.to_numeric(dynamic_curve.get("dynamic_dca_trade_cost_usd"), errors="coerce").fillna(0.0)
        trade_cost_total = float(trade_costs.sum())
        total_traded = float((buy_usd + sell_usd).sum())
        equity_denom = float(equity_usd.abs().mean()) if not equity_usd.dropna().empty else np.nan
        if np.isfinite(equity_denom) and equity_denom > 0.0 and np.isfinite(years) and years > 0.0:
            turnover_per_year = float(total_traded / equity_denom / years)
            cost_drag_per_year = float(trade_cost_total / equity_denom / years)
        exposure = pd.to_numeric(dynamic_curve.get("dynamic_dca_exposure"), errors="coerce")
        avg_exposure = float(exposure.mean()) if exposure.notna().any() else np.nan
        cash_utilization = float(buy_usd.sum() / max(float(len(dynamic_curve)), 1.0)) if len(dynamic_curve) else np.nan

    rows: List[Dict[str, Any]] = []
    for strategy, row in lookup.items():
        cagr = float(row.get("cagr", np.nan)) if pd.notna(row.get("cagr", np.nan)) else np.nan
        fixed_cagr = float(fixed.get("cagr", np.nan)) if pd.notna(fixed.get("cagr", np.nan)) else np.nan
        buy_hold_cagr = float(buy_hold.get("cagr", np.nan)) if pd.notna(buy_hold.get("cagr", np.nan)) else np.nan
        strategy_terminal_value = float(row.get("ending_value", np.nan)) if pd.notna(row.get("ending_value", np.nan)) else np.nan
        if strategy == "dynamic_dca" and np.isfinite(terminal_equity_usd):
            strategy_terminal_value = terminal_equity_usd
        production_row = {
            **row,
            "signal": "dca_risk" if strategy == "dynamic_dca" else "not_applicable",
            "strategy": strategy,
            "cost_bps": float(row.get("embedded_cost_bps", 0.0) or 0.0),
            "months": int(len(dynamic_curve)) if not dynamic_curve.empty else np.nan,
            "volatility": row.get("annualized_volatility", np.nan),
            "policy_family": PRODUCTION_DCA_POLICY_FAMILY
            if strategy == "dynamic_dca"
            else "production_benchmark_reference",
            "signal_direction": "low_dca_risk_buy_high_dca_risk_sell"
            if strategy == "dynamic_dca"
            else "not_applicable",
            "cagr_delta_vs_fixed_dca": float(cagr - fixed_cagr)
            if np.isfinite(cagr) and np.isfinite(fixed_cagr)
            else np.nan,
            "cagr_delta_vs_buy_hold": float(cagr - buy_hold_cagr)
            if np.isfinite(cagr) and np.isfinite(buy_hold_cagr)
            else np.nan,
            "terminal_wealth_delta_vs_fixed_dca": float(strategy_terminal_value - fixed_terminal_value)
            if strategy == "dynamic_dca" and np.isfinite(strategy_terminal_value) and np.isfinite(fixed_terminal_value)
            else np.nan,
            "terminal_wealth_delta_definition": "ending_value_usd_minus_fixed_dca_on_equal_external_cashflows"
            if strategy == "dynamic_dca"
            else "not_applicable",
            "turnover_per_year": turnover_per_year if strategy == "dynamic_dca" else 0.0,
            "avg_exposure": avg_exposure if strategy == "dynamic_dca" else np.nan,
            "cost_drag": trade_cost_total if strategy == "dynamic_dca" else 0.0,
            "cost_drag_per_year": cost_drag_per_year if strategy == "dynamic_dca" else 0.0,
            "execution_lag": "signal_month_close_applied_next_month_close",
            "terminal_equity_usd": terminal_equity_usd if strategy == "dynamic_dca" else np.nan,
            "cash_utilization": cash_utilization if strategy == "dynamic_dca" else np.nan,
        }
        rows.append(production_row)

    curves: List[pd.DataFrame] = []
    if not curve_frame.empty and "date" in curve_frame.columns:
        curve_map = {
            "buy_and_hold": "buy_and_hold_equity",
            "fixed_dca": "fixed_dca_equity",
            "halving_heuristic": "halving_equity",
            "dynamic_dca": "dynamic_dca_equity",
            "cycle_signal": "cycle_equity",
        }
        for strategy, equity_column in curve_map.items():
            if equity_column not in curve_frame.columns:
                continue
            curve = pd.DataFrame(
                {
                    "date": pd.to_datetime(curve_frame["date"], errors="coerce"),
                    "signal": "dca_risk" if strategy == "dynamic_dca" else "not_applicable",
                    "strategy": strategy,
                    "cost_bps": float(lookup.get(strategy, {}).get("embedded_cost_bps", 0.0) or 0.0),
                    "price": pd.to_numeric(curve_frame.get("price"), errors="coerce"),
                    "equity": pd.to_numeric(curve_frame[equity_column], errors="coerce"),
                    "policy_family": PRODUCTION_DCA_POLICY_FAMILY
                    if strategy == "dynamic_dca"
                    else "production_benchmark_reference",
                }
            )
            if strategy == "dynamic_dca":
                curve["applied_exposure"] = pd.to_numeric(curve_frame.get("dynamic_dca_exposure"), errors="coerce")
                curve["buy_usd"] = pd.to_numeric(curve_frame.get("dynamic_dca_buy_usd"), errors="coerce")
                curve["sell_usd"] = pd.to_numeric(curve_frame.get("dynamic_dca_sell_usd"), errors="coerce")
                curve["trade_cost_usd"] = pd.to_numeric(curve_frame.get("dynamic_dca_trade_cost_usd"), errors="coerce")
                curve["account_value_usd"] = pd.to_numeric(curve_frame.get("dynamic_dca_value"), errors="coerce")
                curve["total_contributed_usd"] = pd.to_numeric(
                    curve_frame.get("dynamic_dca_total_contributed"), errors="coerce"
                )
            curves.append(curve)

    trades = pd.DataFrame()
    if not dynamic_curve.empty:
        buy_usd = pd.to_numeric(dynamic_curve.get("dynamic_dca_buy_usd"), errors="coerce").fillna(0.0)
        sell_usd = pd.to_numeric(dynamic_curve.get("dynamic_dca_sell_usd"), errors="coerce").fillna(0.0)
        trade_mask = (buy_usd.abs() + sell_usd.abs()) > 1e-12
        if trade_mask.any():
            trade_cost_series = pd.to_numeric(
                dynamic_curve.get("dynamic_dca_trade_cost_usd", pd.Series(0.0, index=dynamic_curve.index)),
                errors="coerce",
            ).fillna(0.0)
            trades = pd.DataFrame(
                {
                    "date": pd.to_datetime(dynamic_curve.loc[trade_mask, "date"], errors="coerce"),
                    "signal": "dca_risk",
                    "strategy": "dynamic_dca",
                    "cost_bps": 0.0,
                    "target_exposure": np.nan,
                    "turnover": np.nan,
                    "buy_usd": buy_usd.loc[trade_mask].to_numpy(dtype=float),
                    "sell_usd": sell_usd.loc[trade_mask].to_numpy(dtype=float),
                    "trade_cost_usd": trade_cost_series.loc[trade_mask].to_numpy(dtype=float),
                }
            )

    results = pd.DataFrame(rows)
    warnings: List[str] = []
    if "dynamic_dca" not in lookup:
        warnings.append("production_dynamic_dca_unavailable:missing_dynamic_dca_strategy")
    return PracticalStrategyResult(
        results=results,
        curves=pd.concat(curves, ignore_index=True) if curves else pd.DataFrame(),
        trades=trades.reset_index(drop=True) if not trades.empty else trades,
        config={
            "enabled": True,
            "cadence": "monthly",
            "source": "risk_engine.cycle_model._simulate_dynamic_dca",
        },
        warnings=warnings,
    )


def compute_threshold_reachability(
    risk_series: pd.DataFrame,
    *,
    buy_threshold: float,
    sell_threshold: float,
) -> pd.DataFrame:
    frame = _curve_date_index(risk_series)
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "threshold_name",
                "action",
                "signal_column",
                "threshold",
                "comparison",
                "observations",
                "crossing_count",
                "pct_history_at_or_above",
                "pct_history_at_or_below",
                "pct_action_gate_reachable",
                "first_crossing_date",
            ]
        )

    rows: List[Dict[str, Any]] = []
    specs = [
        ("cycle_dynamic_dca_buy_threshold", "buy", "dca_risk", 1.0 - float(buy_threshold), "<="),
        ("cycle_dynamic_dca_sell_threshold", "sell", "dca_risk", float(sell_threshold), ">="),
    ]
    for threshold_name, action, column, threshold, comparison in specs:
        if column not in frame.columns:
            values = pd.Series(dtype=float)
            dates = pd.Series(dtype="datetime64[ns]")
        else:
            values = pd.to_numeric(frame[column], errors="coerce").shift(1)
            dates = pd.to_datetime(frame["date"], errors="coerce") if "date" in frame.columns else pd.Series(frame.index, index=frame.index)
        clean = values.dropna()
        at_or_above = values >= threshold
        at_or_below = values <= threshold
        crossings = (at_or_below if comparison == "<=" else at_or_above) & values.notna()
        first_crossing = pd.NaT
        if crossings.any():
            first_crossing = pd.to_datetime(dates.loc[crossings].dropna().iloc[0], errors="coerce")
        observations = int(clean.shape[0])
        rows.append(
            {
                "threshold_name": threshold_name,
                "action": action,
                "signal_column": column,
                "threshold": threshold,
                "comparison": comparison,
                "observations": observations,
                "crossing_count": int(crossings.sum()),
                "pct_history_at_or_above": float(at_or_above.sum() / observations) if observations else np.nan,
                "pct_history_at_or_below": float(at_or_below.sum() / observations) if observations else np.nan,
                "pct_action_gate_reachable": float(crossings.sum() / observations) if observations else np.nan,
                "first_crossing_date": first_crossing,
            }
        )
    return pd.DataFrame(rows)


def _baseline_exposures(price: pd.Series, seed: int) -> Dict[str, pd.Series]:
    monthly_price = _month_end_series(price)
    momentum = monthly_price.pct_change(6, fill_method=None)
    drawdown = monthly_price / monthly_price.cummax().replace({0.0: np.nan}) - 1.0
    rng = np.random.default_rng(seed)
    random_target = pd.Series(rng.choice([0.0, 0.5, 1.0], size=len(monthly_price)), index=monthly_price.index, dtype=float)
    return {
        "baseline_buy_hold": pd.Series(1.0, index=monthly_price.index, dtype=float),
        "baseline_half_allocation": pd.Series(0.5, index=monthly_price.index, dtype=float),
        "baseline_momentum_6m": (momentum > 0.0).astype(float).where(momentum.notna(), 0.5),
        "baseline_drawdown_buy_deep": pd.Series(np.where(drawdown <= -0.40, 1.0, 0.5), index=monthly_price.index, dtype=float),
        "baseline_random_timing_seeded": random_target,
    }


def evaluate_practical_strategies(series: pd.DataFrame, config: EvaluationConfig) -> PracticalStrategyResult:
    if "btc_price" not in series.columns:
        return PracticalStrategyResult(
            results=pd.DataFrame(),
            curves=pd.DataFrame(),
            trades=pd.DataFrame(),
            config={"enabled": False},
            warnings=["practical_strategies_unavailable:missing_btc_price"],
        )

    price = _month_end_series(series["btc_price"])
    signal_names = [metric.name for metric in config.metrics if metric.confirmatory and metric.name in series.columns]
    if price.empty or not signal_names:
        return PracticalStrategyResult(
            results=pd.DataFrame(),
            curves=pd.DataFrame(),
            trades=pd.DataFrame(),
            config={"enabled": False},
            warnings=["practical_strategies_unavailable:empty_price_or_signals"],
        )

    cost_grid = [0.0, 25.0] if config.smoke_mode else [0.0, 10.0, 25.0, 50.0, 100.0]
    result_rows: List[Dict[str, Any]] = []
    curve_rows: List[pd.DataFrame] = []
    trade_rows: List[pd.DataFrame] = []

    baselines = _baseline_exposures(price, int(config.seed) + 7001)
    for strategy_name, exposure in baselines.items():
        for cost_bps in cost_grid:
            summary, curve, trades = _simulate_allocation(
                price,
                exposure,
                cost_bps=cost_bps,
                strategy=strategy_name,
                signal="baseline",
            )
            result_rows.append({**summary, "policy_family": "baseline", "signal_direction": "not_applicable"})
            if not curve.empty:
                curve_rows.append(curve)
            if not trades.empty:
                trade_rows.append(trades)

    baseline_lookup = {
        (row["strategy"], row["cost_bps"]): row
        for row in result_rows
        if row.get("signal") == "baseline"
    }

    dca_lookup: Dict[float, Dict[str, Any]] = {}
    fixed_multiplier = pd.Series(1.0, index=price.index, dtype=float)
    rng = np.random.default_rng(int(config.seed) + 8101)
    random_multiplier = pd.Series(rng.choice([0.25, 0.75, 1.25, 1.75], size=len(price)), index=price.index, dtype=float)
    dca_policies: Dict[str, pd.Series] = {
        "baseline_fixed_monthly_dca": fixed_multiplier,
        "baseline_random_same_cashflow_dca": random_multiplier,
    }
    if "dca_risk" in series.columns:
        dca_signal = _month_end_series(series["dca_risk"]).reindex(price.index)
        favorable = (1.0 - pd.to_numeric(dca_signal, errors="coerce").clip(0.0, 1.0)).fillna(0.5)
        dca_policies["risk_weighted_dca"] = (0.25 + 1.50 * favorable).clip(0.0, 2.0)

    for strategy_name, multiplier in dca_policies.items():
        for cost_bps in cost_grid:
            summary, curve, trades = _simulate_dca_cashflow(
                price,
                multiplier,
                cost_bps=cost_bps,
                strategy=strategy_name,
                signal="dca_risk" if strategy_name == "risk_weighted_dca" else "baseline",
            )
            if not summary:
                continue
            if strategy_name == "baseline_fixed_monthly_dca":
                dca_lookup[float(cost_bps)] = summary
            fixed = dca_lookup.get(float(cost_bps), {})
            result_rows.append(
                {
                    **summary,
                    "policy_family": "dca_cashflow",
                    "signal_direction": "low_dca_risk_more_buying" if strategy_name == "risk_weighted_dca" else "not_applicable",
                    "cagr_delta_vs_fixed_dca": float(summary["cagr"] - fixed.get("cagr", np.nan))
                    if np.isfinite(summary.get("cagr", np.nan)) and np.isfinite(fixed.get("cagr", np.nan))
                    else np.nan,
                    "terminal_wealth_delta_vs_fixed_dca": float(
                        summary["terminal_equity_usd"] - fixed.get("terminal_equity_usd", np.nan)
                    )
                    if np.isfinite(summary.get("terminal_equity_usd", np.nan))
                    and np.isfinite(fixed.get("terminal_equity_usd", np.nan))
                    else np.nan,
                }
            )
            if not curve.empty:
                curve_rows.append(curve)
            if not trades.empty:
                trade_rows.append(trades)

    for signal in signal_names:
        monthly_signal = _month_end_series(series[signal]).reindex(price.index)
        direction = _direction(signal)
        continuous = _score_to_exposure(monthly_signal, direction, "continuous")
        policies = {
            "metric_continuous_allocation": continuous,
            "metric_allocation_bands": _score_to_exposure(monthly_signal, direction, "bands"),
            "metric_hysteresis_bands": _hysteresis(_score_to_exposure(monthly_signal, direction, "bands")),
            "metric_conservative_autopilot": _score_to_exposure(monthly_signal, direction, "conservative"),
        }
        for strategy_name, exposure in policies.items():
            for cost_bps in cost_grid:
                summary, curve, trades = _simulate_allocation(
                    price,
                    exposure,
                    cost_bps=cost_bps,
                    strategy=strategy_name,
                    signal=signal,
                )
                buy_hold = baseline_lookup.get(("baseline_buy_hold", float(cost_bps)), {})
                half = baseline_lookup.get(("baseline_half_allocation", float(cost_bps)), {})
                summary = {
                    **summary,
                    "policy_family": "metric_policy",
                    "signal_direction": direction,
                    "cagr_delta_vs_buy_hold": float(summary["cagr"] - buy_hold.get("cagr", np.nan))
                    if np.isfinite(summary.get("cagr", np.nan)) and np.isfinite(buy_hold.get("cagr", np.nan))
                    else np.nan,
                    "calmar_delta_vs_half_allocation": float(summary["calmar"] - half.get("calmar", np.nan))
                    if np.isfinite(summary.get("calmar", np.nan)) and np.isfinite(half.get("calmar", np.nan))
                    else np.nan,
                    "max_drawdown_delta_vs_buy_hold": float(abs(summary["max_drawdown"]) - abs(buy_hold.get("max_drawdown", np.nan)))
                    if np.isfinite(summary.get("max_drawdown", np.nan)) and np.isfinite(buy_hold.get("max_drawdown", np.nan))
                    else np.nan,
                    "drawdown_reduction_vs_buy_hold": float(abs(buy_hold.get("max_drawdown", np.nan)) - abs(summary["max_drawdown"]))
                    if np.isfinite(summary.get("max_drawdown", np.nan)) and np.isfinite(buy_hold.get("max_drawdown", np.nan))
                    else np.nan,
                }
                result_rows.append(summary)
                if not curve.empty:
                    curve_rows.append(curve)
                if not trades.empty:
                    trade_rows.append(trades)

    results = pd.DataFrame(result_rows)
    if not results.empty:
        results["passes_turnover_guardrail"] = pd.to_numeric(results["turnover_per_year"], errors="coerce") <= float(
            config.claim_gates.max_turnover_per_year
        )
        results["passes_cost_drag_guardrail"] = pd.to_numeric(results["cost_drag_per_year"], errors="coerce") <= float(
            config.claim_gates.max_cost_drag
        )
        results = results.sort_values(["signal", "strategy", "cost_bps"]).reset_index(drop=True)
    curves = pd.concat(curve_rows, ignore_index=True) if curve_rows else pd.DataFrame()
    trades = pd.concat(trade_rows, ignore_index=True) if trade_rows else pd.DataFrame()
    warnings: List[str] = []
    if results.empty:
        warnings.append("practical_strategies_unavailable:no_results")
    return PracticalStrategyResult(
        results=results,
        curves=curves,
        trades=trades,
        config={
            "enabled": True,
            "cadence": "monthly",
            "execution_lag": "target_from_month_close_applied_next_month",
            "cost_grid_bps": cost_grid,
            "policies_are_predeclared": True,
            "same_return_stream_for_all_strategies": True,
        },
        warnings=warnings,
    )
