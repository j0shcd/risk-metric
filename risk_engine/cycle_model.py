from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, Iterable, List

import numpy as np
import pandas as pd

from .config import RuntimeConfig


@dataclass(frozen=True)
class CycleModelOutput:
    feature_snapshots: pd.DataFrame
    regime_scores: pd.DataFrame
    signal_decisions: pd.DataFrame
    backtest_report: pd.DataFrame
    metric_audit: pd.DataFrame
    migration_plan: str
    daily_projection: pd.DataFrame


def _monthly_last(series: pd.Series) -> pd.Series:
    return series.resample("M").last()


def _monthly_mean(series: pd.Series) -> pd.Series:
    return series.resample("M").mean()


def _monthly_sum(series: pd.Series) -> pd.Series:
    return series.resample("M").sum(min_count=1)


def _expanding_percentile(series: pd.Series, min_history: int) -> pd.Series:
    values = series.astype(float)
    out = pd.Series(index=values.index, dtype=float)
    for i in range(len(values)):
        current = values.iloc[i]
        if np.isnan(current):
            out.iloc[i] = np.nan
            continue
        history = values.iloc[: i + 1].dropna()
        if len(history) < min_history:
            out.iloc[i] = np.nan
            continue
        out.iloc[i] = float((history <= current).mean())
    return out.clip(0.0, 1.0)


def _category_mean(frame: pd.DataFrame, columns: Iterable[str]) -> pd.Series:
    valid = [col for col in columns if col in frame.columns]
    if not valid:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return frame[valid].mean(axis=1, skipna=True)


def _logistic_probability(score: pd.Series, center: float = 0.65, slope: float = 10.0) -> pd.Series:
    z = (score.astype(float) - center) * slope
    clipped = z.clip(-20.0, 20.0)
    return (1.0 / (1.0 + np.exp(-clipped))).clip(0.0, 1.0)


def _max_drawdown(equity: pd.Series) -> float:
    clean = equity.dropna()
    if clean.empty:
        return float("nan")
    peak = clean.cummax()
    drawdown = clean / peak.replace({0.0: np.nan}) - 1.0
    return float(drawdown.min())


def _halving_heuristic_position(index: pd.DatetimeIndex, hold_months: int = 30) -> pd.Series:
    halving_dates = [
        pd.Timestamp("2012-11-28"),
        pd.Timestamp("2016-07-09"),
        pd.Timestamp("2020-05-11"),
        pd.Timestamp("2024-04-20"),
    ]
    position = pd.Series(0.0, index=index, dtype=float)
    for event in halving_dates:
        start = event.to_period("M").to_timestamp("M")
        end = (event + pd.DateOffset(months=hold_months)).to_period("M").to_timestamp("M")
        mask = (index >= start) & (index <= end)
        position.loc[mask] = 1.0
    return position


def _build_monthly_inputs(
    btc_price: pd.Series,
    onchain_frame: pd.DataFrame,
    context_frame: pd.DataFrame,
) -> pd.DataFrame:
    base_index = btc_price.index

    def _indexed_series(frame: pd.DataFrame, column: str) -> pd.Series:
        if column in frame.columns:
            return frame[column]
        return pd.Series(index=base_index, dtype=float)

    monthly = pd.DataFrame(index=_monthly_last(btc_price).index)
    monthly["btc_price"] = _monthly_last(btc_price)
    monthly["btc_volume_usd"] = _monthly_sum(_indexed_series(context_frame, "btc_volume_usd"))
    monthly["mvrv_z_score"] = _monthly_last(_indexed_series(onchain_frame, "mvrv_z_score"))
    monthly["puell_multiple"] = _monthly_last(_indexed_series(onchain_frame, "puell_multiple"))
    monthly["supply_in_profit"] = _monthly_last(_indexed_series(onchain_frame, "supply_in_profit"))

    monthly["google_trends_interest"] = _monthly_mean(
        _indexed_series(context_frame, "google_trends_interest")
    )
    monthly["wikipedia_pageviews"] = _monthly_sum(
        _indexed_series(context_frame, "wikipedia_pageviews")
    )
    monthly["reddit_post_volume"] = _monthly_sum(
        _indexed_series(context_frame, "reddit_post_volume")
    )

    monthly["dxy"] = _monthly_last(_indexed_series(context_frame, "dxy").ffill())
    monthly["real_yield_10y"] = _monthly_last(_indexed_series(context_frame, "real_yield_10y").ffill())
    monthly["net_liquidity"] = _monthly_last(_indexed_series(context_frame, "net_liquidity").ffill())
    return monthly


def _build_feature_snapshot(monthly: pd.DataFrame, cfg: RuntimeConfig) -> pd.DataFrame:
    frame = monthly.copy()
    frame["price_to_48m_trend"] = frame["btc_price"] / frame["btc_price"].rolling(48, min_periods=24).mean()
    frame["drawdown_from_ath"] = (
        frame["btc_price"] / frame["btc_price"].cummax().replace({0.0: np.nan}) - 1.0
    ).clip(-1.0, 0.0)

    frame["volume_accel_3m_12m"] = (
        frame["btc_volume_usd"].rolling(3, min_periods=2).mean()
        / frame["btc_volume_usd"].rolling(12, min_periods=6).mean().replace({0.0: np.nan})
    )
    monthly_returns = frame["btc_price"].pct_change(fill_method=None)
    frame["abs_monthly_return"] = monthly_returns.abs()
    frame["realized_vol_6m"] = np.log(frame["btc_price"]).diff().rolling(6, min_periods=3).std(ddof=0) * np.sqrt(12.0)
    frame["realized_vol_3m"] = np.log(frame["btc_price"]).diff().rolling(3, min_periods=2).std(ddof=0) * np.sqrt(12.0)
    frame["realized_vol_12m"] = np.log(frame["btc_price"]).diff().rolling(12, min_periods=6).std(ddof=0) * np.sqrt(12.0)

    # Blow-off / capitulation channels from free-market observables.
    frame["vol_spread_3m_12m"] = frame["realized_vol_3m"] - frame["realized_vol_12m"]
    frame["return_convexity_1_3"] = monthly_returns - (frame["btc_price"].pct_change(3, fill_method=None) / 3.0)
    frame["volume_accel_log_1_12"] = (
        np.log1p(frame["btc_volume_usd"].clip(lower=0.0))
        - np.log1p(frame["btc_volume_usd"].rolling(12, min_periods=6).mean().clip(lower=0.0))
    )

    frame["wiki_yoy_growth"] = frame["wikipedia_pageviews"] / frame["wikipedia_pageviews"].shift(12) - 1.0
    frame["reddit_yoy_growth"] = frame["reddit_post_volume"] / frame["reddit_post_volume"].shift(12) - 1.0
    frame["google_trends_3m"] = frame["google_trends_interest"].rolling(3, min_periods=2).mean()
    frame["attention_1m"] = _category_mean(frame, ["google_trends_interest", "wikipedia_pageviews", "reddit_post_volume"])
    attention_mean = frame["attention_1m"].rolling(12, min_periods=6).mean()
    attention_std = frame["attention_1m"].rolling(12, min_periods=6).std(ddof=0).replace({0.0: np.nan})
    frame["attention_z_spike_12m"] = (frame["attention_1m"] - attention_mean) / attention_std
    frame["drawdown_velocity_3m"] = frame["drawdown_from_ath"].diff(3) / 3.0

    frame["net_liquidity_yoy"] = frame["net_liquidity"] / frame["net_liquidity"].shift(12) - 1.0
    frame["dxy_inverted"] = -1.0 * frame["dxy"]
    frame["real_yield_inverted"] = -1.0 * frame["real_yield_10y"]

    oriented_features = {
        "pct_price_to_48m_trend": "price_to_48m_trend",
        "pct_mvrv_z_score": "mvrv_z_score",
        "pct_puell_multiple": "puell_multiple",
        "pct_drawdown_recovery": "drawdown_from_ath",
        "pct_volume_accel_3m_12m": "volume_accel_3m_12m",
        "pct_abs_monthly_return": "abs_monthly_return",
        "pct_realized_vol_6m": "realized_vol_6m",
        "pct_supply_in_profit": "supply_in_profit",
        "pct_vol_spread_3m_12m": "vol_spread_3m_12m",
        "pct_return_convexity_1_3": "return_convexity_1_3",
        "pct_volume_accel_log_1_12": "volume_accel_log_1_12",
        "pct_attention_z_spike_12m": "attention_z_spike_12m",
        "pct_drawdown_velocity_3m": "drawdown_velocity_3m",
        "pct_google_trends_3m": "google_trends_3m",
        "pct_wiki_yoy_growth": "wiki_yoy_growth",
        "pct_reddit_yoy_growth": "reddit_yoy_growth",
        "pct_net_liquidity_yoy": "net_liquidity_yoy",
        "pct_dxy_inverted": "dxy_inverted",
        "pct_real_yield_inverted": "real_yield_inverted",
    }
    for output_col, input_col in oriented_features.items():
        frame[output_col] = _expanding_percentile(frame[input_col], min_history=cfg.cycle_min_history_months)

    frame["valuation_hot"] = _category_mean(
        frame,
        ["pct_price_to_48m_trend", "pct_mvrv_z_score", "pct_puell_multiple", "pct_drawdown_recovery"],
    )
    frame["speculation_hot"] = _category_mean(
        frame,
        ["pct_volume_accel_3m_12m", "pct_abs_monthly_return", "pct_realized_vol_6m", "pct_supply_in_profit"],
    )
    frame["attention_hot"] = _category_mean(
        frame,
        ["pct_google_trends_3m", "pct_wiki_yoy_growth", "pct_reddit_yoy_growth"],
    )
    frame["macro_hot"] = _category_mean(
        frame,
        ["pct_net_liquidity_yoy", "pct_dxy_inverted", "pct_real_yield_inverted"],
    )

    frame["valuation_cold"] = 1.0 - frame["valuation_hot"]
    frame["speculation_cold"] = 1.0 - frame["speculation_hot"]
    frame["attention_cold"] = 1.0 - frame["attention_hot"]
    frame["macro_cold"] = 1.0 - frame["macro_hot"]

    frame["price_extremity_pct"] = frame["pct_price_to_48m_trend"]
    frame["momentum_exhaustion_pct"] = _category_mean(
        frame,
        ["pct_vol_spread_3m_12m", "pct_return_convexity_1_3", "pct_volume_accel_log_1_12"],
    ).clip(0.0, 1.0)
    frame["attention_blowoff_pct"] = _category_mean(
        frame,
        ["pct_attention_z_spike_12m", "pct_google_trends_3m"],
    ).clip(0.0, 1.0)
    return frame


def _weighted_category_composite(frame: pd.DataFrame, columns: Dict[str, str], weights: Dict[str, float]) -> pd.Series:
    numerator = pd.Series(0.0, index=frame.index, dtype=float)
    denominator = pd.Series(0.0, index=frame.index, dtype=float)
    for category, col in columns.items():
        base_weight = float(weights.get(category, 0.0))
        if base_weight <= 0.0 or col not in frame.columns:
            continue
        value = frame[col]
        mask = value.notna()
        numerator += (base_weight * value.fillna(0.0))
        denominator += base_weight * mask.astype(float)
    return (numerator / denominator.replace({0.0: np.nan})).clip(0.0, 1.0)


def _build_regime_scores(feature_frame: pd.DataFrame, cfg: RuntimeConfig) -> pd.DataFrame:
    heat_columns = {
        "valuation": "valuation_hot",
        "speculation": "speculation_hot",
        "attention": "attention_hot",
        "macro": "macro_hot",
    }
    cold_columns = {
        "valuation": "valuation_cold",
        "speculation": "speculation_cold",
        "attention": "attention_cold",
        "macro": "macro_cold",
    }

    regime = pd.DataFrame(index=feature_frame.index)
    regime["heat_score"] = _weighted_category_composite(feature_frame, heat_columns, cfg.cycle_category_weights)
    regime["cold_score"] = _weighted_category_composite(feature_frame, cold_columns, cfg.cycle_category_weights)

    categories_available = pd.concat(
        [
            feature_frame["valuation_hot"].notna().astype(float),
            feature_frame["speculation_hot"].notna().astype(float),
            feature_frame["attention_hot"].notna().astype(float),
            feature_frame["macro_hot"].notna().astype(float),
        ],
        axis=1,
    )
    regime["category_coverage"] = categories_available.mean(axis=1).clip(0.0, 1.0)

    raw_feature_columns = [
        "price_to_48m_trend",
        "mvrv_z_score",
        "puell_multiple",
        "volume_accel_3m_12m",
        "google_trends_3m",
        "wikipedia_pageviews",
        "reddit_post_volume",
        "net_liquidity_yoy",
        "dxy",
        "real_yield_10y",
    ]
    raw_available = pd.concat(
        [feature_frame.get(col, pd.Series(index=feature_frame.index, dtype=float)).notna().astype(float) for col in raw_feature_columns],
        axis=1,
    )
    regime["feature_coverage"] = raw_available.mean(axis=1).clip(0.0, 1.0)
    regime["confidence"] = (0.5 * regime["category_coverage"] + 0.5 * regime["feature_coverage"]).clip(0.0, 1.0)

    base_frenzy = _logistic_probability(regime["heat_score"], center=0.65, slope=10.0)
    base_accum = _logistic_probability(regime["cold_score"], center=0.65, slope=10.0)
    shrink = (0.4 + 0.6 * regime["confidence"]).clip(0.0, 1.0)
    regime["p_frenzy"] = (0.5 + (base_frenzy - 0.5) * shrink).clip(0.0, 1.0)
    regime["p_accumulation"] = (0.5 + (base_accum - 0.5) * shrink).clip(0.0, 1.0)
    return regime


def _top_trigger_categories(row: pd.Series, suffix: str, limit: int = 2) -> str:
    candidates = {
        "valuation": row.get(f"valuation_{suffix}"),
        "speculation": row.get(f"speculation_{suffix}"),
        "attention": row.get(f"attention_{suffix}"),
        "macro": row.get(f"macro_{suffix}"),
    }
    scored = [(name, float(value)) for name, value in candidates.items() if pd.notna(value)]
    if not scored:
        return ""
    scored.sort(key=lambda item: item[1], reverse=True)
    return ",".join([name for name, _ in scored[:limit]])


def _build_signal_decisions(feature_frame: pd.DataFrame, regime_scores: pd.DataFrame, cfg: RuntimeConfig) -> pd.DataFrame:
    decisions = pd.DataFrame(index=regime_scores.index)
    decisions["regime"] = "HOLD"
    decisions["trigger_features"] = ""
    decisions["cooldown_state"] = 0
    decisions["position"] = 0.0

    buy_ready = (
        regime_scores["p_accumulation"]
        .ge(cfg.cycle_buy_threshold)
        .rolling(cfg.cycle_confirmation_months, min_periods=cfg.cycle_confirmation_months)
        .sum()
        .ge(cfg.cycle_confirmation_months)
    )
    sell_ready = (
        regime_scores["p_frenzy"]
        .ge(cfg.cycle_sell_threshold)
        .rolling(cfg.cycle_confirmation_months, min_periods=cfg.cycle_confirmation_months)
        .sum()
        .ge(cfg.cycle_confirmation_months)
    )

    cooldown = 0
    position = 0.0
    for date in decisions.index:
        decision = "HOLD"
        trigger = ""

        if cooldown > 0:
            cooldown -= 1

        can_buy = bool(buy_ready.loc[date]) if pd.notna(buy_ready.loc[date]) else False
        can_sell = bool(sell_ready.loc[date]) if pd.notna(sell_ready.loc[date]) else False

        if cooldown == 0 and (can_buy or can_sell):
            if can_buy and can_sell:
                buy_excess = float(regime_scores.loc[date, "p_accumulation"] - cfg.cycle_buy_threshold)
                sell_excess = float(regime_scores.loc[date, "p_frenzy"] - cfg.cycle_sell_threshold)
                can_buy = buy_excess >= sell_excess
                can_sell = not can_buy

            if can_buy and position <= 0.0:
                decision = "BUY"
                position = 1.0
                trigger = _top_trigger_categories(feature_frame.loc[date], suffix="cold")
                cooldown = cfg.cycle_cooldown_months
            elif can_sell and position >= 1.0:
                decision = "SELL"
                position = 0.0
                trigger = _top_trigger_categories(feature_frame.loc[date], suffix="hot")
                cooldown = cfg.cycle_cooldown_months

        decisions.loc[date, "regime"] = decision
        decisions.loc[date, "trigger_features"] = trigger
        decisions.loc[date, "cooldown_state"] = int(cooldown)
        decisions.loc[date, "position"] = float(position)

    return decisions


def _build_backtest_report(monthly_price: pd.Series, decisions: pd.DataFrame) -> pd.DataFrame:
    price = monthly_price.astype(float).dropna()
    aligned = decisions.reindex(price.index)
    returns = price.pct_change(fill_method=None).fillna(0.0)

    position = aligned["position"].fillna(0.0)
    strategy_returns = position.shift(1).fillna(0.0) * returns
    strategy_equity = (1.0 + strategy_returns).cumprod()

    buyhold_equity = (1.0 + returns).cumprod()

    dca_units = (1.0 / price.replace({0.0: np.nan})).fillna(0.0)
    dca_value = dca_units.cumsum() * price
    dca_invested = pd.Series(np.arange(1, len(price) + 1, dtype=float), index=price.index)
    dca_equity = dca_value / dca_invested
    dca_returns = dca_equity.pct_change(fill_method=None).fillna(0.0)

    halving_position = _halving_heuristic_position(price.index)
    halving_returns = halving_position.shift(1).fillna(0.0) * returns
    halving_equity = (1.0 + halving_returns).cumprod()

    years = max(len(price) / 12.0, 1.0 / 12.0)
    strategy_total = float(strategy_equity.iloc[-1] - 1.0)
    buyhold_total = float(buyhold_equity.iloc[-1] - 1.0)
    dca_total = float(dca_equity.iloc[-1] - 1.0)
    halving_total = float(halving_equity.iloc[-1] - 1.0)
    strategy_cagr = float(strategy_equity.iloc[-1] ** (1.0 / years) - 1.0)
    trades = int((aligned["regime"] != "HOLD").sum())
    turnover = float(trades / years)

    benchmark_comparison = {
        "buy_and_hold_total_return": buyhold_total,
        "buy_and_hold_cagr": float(buyhold_equity.iloc[-1] ** (1.0 / years) - 1.0),
        "buy_and_hold_max_drawdown": _max_drawdown(buyhold_equity),
        "dca_total_return": dca_total,
        "dca_cagr": float(dca_equity.iloc[-1] ** (1.0 / years) - 1.0),
        "dca_max_drawdown": _max_drawdown((1.0 + dca_returns).cumprod()),
        "halving_total_return": halving_total,
        "halving_cagr": float(halving_equity.iloc[-1] ** (1.0 / years) - 1.0),
        "halving_max_drawdown": _max_drawdown(halving_equity),
    }

    report = pd.DataFrame(
        [
            {
                "window": f"{price.index.min().date().isoformat()}:{price.index.max().date().isoformat()}",
                "trades": trades,
                "cycle_capture": (
                    float(strategy_total / buyhold_total)
                    if np.isfinite(buyhold_total) and abs(buyhold_total) > 1e-12
                    else np.nan
                ),
                "max_drawdown": _max_drawdown(strategy_equity),
                "turnover": turnover,
                "total_return": strategy_total,
                "cagr": strategy_cagr,
                "benchmark_comparison": json.dumps(benchmark_comparison, sort_keys=True),
            }
        ]
    )
    return report


def _metric_audit_frame() -> pd.DataFrame:
    rows = [
        ("btc_trend_extension_50d_350d", "recalibrate", "Keep for daily heat, replace in cycle with 48m trend stretch."),
        ("btc_running_roi_1y", "recalibrate", "Downgrade as standalone; absorbed into broader valuation/speculation blocks."),
        ("btc_log_reg_deviation", "keep", "Still useful as long-horizon valuation proxy."),
        ("btc_drawdown_from_ath", "keep", "Retain as cold-regime context."),
        ("btc_realized_vol_30d", "recalibrate", "Use slower monthly realized-vol channel in cycle model."),
        ("total_trend_extension_50d_350d", "recalibrate", "Retain daily, not primary in monthly cycle core."),
        ("total_running_roi_1y", "drop", "Redundant with slower BTC-led cycle feature stack."),
        ("total_log_reg_deviation", "recalibrate", "Context-only signal for broader risk regime."),
        ("total_drawdown_from_ath", "drop", "Lower marginal value after explicit cycle position model."),
        ("total_realized_vol_30d", "drop", "Too reactive for multi-year regime decisions."),
        ("btc_dominance_proxy", "replace", "Replace with macro/liquidity block + attention breadth."),
        ("mvrv_z_score", "keep", "Primary valuation anchor."),
        ("puell_multiple", "keep", "Primary miner-cycle valuation anchor."),
        ("supply_in_profit", "keep", "Useful cycle saturation context."),
        ("supply_in_loss", "recalibrate", "Derived counterpart; reduced standalone weight."),
        ("youtube_interest", "drop", "Short-horizon and unstable availability."),
        ("google_trends_interest", "keep", "Core attention component."),
        ("coinbase_app_rank_proxy", "drop", "Experimental and noisy; keep only as optional diagnostic."),
        ("fear_greed_index", "recalibrate", "Secondary sentiment context, not a primary cycle trigger."),
    ]
    frame = pd.DataFrame(rows, columns=["metric", "action", "notes"])
    return frame.sort_values("metric").reset_index(drop=True)


def _migration_plan_markdown() -> str:
    return "\n".join(
        [
            "# Cycle Model Migration Plan",
            "",
            "1. Preserve current daily risk outputs and all existing web contract keys.",
            "2. Add monthly cycle probabilities (`cycle_p_frenzy`, `cycle_p_accumulation`) and signal fields side-by-side.",
            "3. Publish monthly artifacts (`cycle_feature_snapshots_monthly.csv`, `cycle_regime_scores_monthly.csv`, `cycle_signal_decisions_monthly.csv`).",
            "4. Track metric keep/recalibrate/replace/drop decisions in `cycle_metric_audit.csv`.",
            "5. Compare cycle strategy against buy-and-hold, DCA, and naive halving benchmark each run.",
        ]
    )


def build_cycle_model(
    cfg: RuntimeConfig,
    btc_price: pd.Series,
    onchain_frame: pd.DataFrame,
    context_frame: pd.DataFrame,
    daily_index: pd.DatetimeIndex,
) -> CycleModelOutput:
    monthly_inputs = _build_monthly_inputs(
        btc_price=btc_price,
        onchain_frame=onchain_frame,
        context_frame=context_frame,
    )
    monthly_inputs = monthly_inputs[monthly_inputs.index >= pd.Timestamp("2013-01-31")]

    feature_snapshots = _build_feature_snapshot(monthly_inputs, cfg)
    regime_scores = _build_regime_scores(feature_snapshots, cfg)
    signal_decisions = _build_signal_decisions(feature_snapshots, regime_scores, cfg)
    backtest_report = _build_backtest_report(feature_snapshots["btc_price"], signal_decisions)
    metric_audit = _metric_audit_frame()
    migration_plan = _migration_plan_markdown()

    daily_projection = pd.DataFrame(index=daily_index)
    daily_projection["cycle_heat_score"] = regime_scores["heat_score"].reindex(daily_index, method="ffill")
    daily_projection["cycle_cold_score"] = regime_scores["cold_score"].reindex(daily_index, method="ffill")
    daily_projection["cycle_p_frenzy"] = regime_scores["p_frenzy"].reindex(daily_index, method="ffill")
    daily_projection["cycle_p_accumulation"] = regime_scores["p_accumulation"].reindex(daily_index, method="ffill")
    daily_projection["cycle_confidence"] = regime_scores["confidence"].reindex(daily_index, method="ffill")
    daily_projection["cycle_position"] = signal_decisions["position"].reindex(daily_index, method="ffill")
    daily_projection["cycle_signal_regime"] = signal_decisions["regime"].reindex(daily_index, method="ffill")
    daily_projection["cycle_signal_cooldown_state"] = signal_decisions["cooldown_state"].reindex(daily_index, method="ffill")
    daily_projection["price_extremity_pct"] = feature_snapshots["price_extremity_pct"].reindex(daily_index, method="ffill")
    daily_projection["momentum_exhaustion_pct"] = feature_snapshots["momentum_exhaustion_pct"].reindex(
        daily_index,
        method="ffill",
    )
    daily_projection["attention_blowoff_pct"] = feature_snapshots["attention_blowoff_pct"].reindex(
        daily_index,
        method="ffill",
    )

    return CycleModelOutput(
        feature_snapshots=feature_snapshots,
        regime_scores=regime_scores,
        signal_decisions=signal_decisions,
        backtest_report=backtest_report,
        metric_audit=metric_audit,
        migration_plan=migration_plan,
        daily_projection=daily_projection,
    )
