from __future__ import annotations

import argparse

import pandas as pd

from risk_engine.config import load_runtime_config
from risk_engine.pipeline import run_pipeline, write_outputs
from risk_engine.sources.btc_price_backfill import refresh_btc_daily_from_binance
from risk_engine.sources.market import load_btc_price, load_total_market_cap
from risk_engine.sources.onchain import load_onchain_metrics
from risk_engine.sources.social import load_social_metrics
from risk_engine.validation import write_sanity_report


def _backfill_full() -> None:
    cfg = load_runtime_config()
    try:
        refresh_btc_daily_from_binance(cfg)
    except Exception as exc:
        print(f"BTC daily refresh skipped: {exc}")
    result = run_pipeline(cfg)
    write_outputs(result, cfg.output_dir)
    write_sanity_report(result.series, cfg.output_dir)
    print("Backfill completed. Outputs refreshed.")


def _backfill_total_market_only() -> None:
    cfg = load_runtime_config()
    btc = load_btc_price(cfg)
    series = load_total_market_cap(cfg, index=btc.index)

    store_path = cfg.total_marketcap_csv or (cfg.cache_dir / "total_marketcap.csv")
    if store_path.exists():
        frame = pd.read_csv(store_path, parse_dates=["Date"])
        frame = frame.dropna(subset=["total_market_cap"]).sort_values("Date")
        if frame.empty:
            print(f"No usable total market cap rows in {store_path}")
        else:
            latest = frame.iloc[-1]
            print(
                f"Total market cap store updated: {store_path} | rows={len(frame)} | "
                f"latest={latest['Date'].date()} | value={float(latest['total_market_cap']):.2f}"
            )
    else:
        print(f"No total market cap store found at {store_path}")

    print(f"Aligned series points available in current BTC window: {int(series.notna().sum())}")


def _backfill_social_only() -> None:
    cfg = load_runtime_config()
    btc = load_btc_price(cfg)
    social = load_social_metrics(cfg, index=btc.index)

    youtube_count = int(social["youtube_interest"].notna().sum()) if "youtube_interest" in social.columns else 0
    trends_count = int(social["google_trends_interest"].notna().sum()) if "google_trends_interest" in social.columns else 0
    coinbase_count = int(social["coinbase_app_rank_proxy"].notna().sum()) if "coinbase_app_rank_proxy" in social.columns else 0

    print("Social backfill complete.")
    print(f" - youtube_interest points: {youtube_count}")
    print(f" - google_trends_interest points: {trends_count}")
    print(f" - coinbase_app_rank_proxy points: {coinbase_count}")


def _backfill_onchain_only() -> None:
    cfg = load_runtime_config()
    btc = load_btc_price(cfg)
    onchain = load_onchain_metrics(cfg, index=btc.index)

    store_path = cfg.onchain_fallback_csv or (cfg.cache_dir / "onchain_metrics.csv")
    if store_path.exists():
        frame = pd.read_csv(store_path, parse_dates=["Date"]).sort_values("Date")
        latest_date = frame["Date"].max().date() if not frame.empty else None
        print(f"On-chain store updated: {store_path} | rows={len(frame)} | latest={latest_date}")
    else:
        print(f"No on-chain store found at {store_path}")

    for column in ["mvrv_ratio_z_proxy", "puell_multiple", "mvrv_implied_profitability_proxy"]:
        count = int(onchain[column].notna().sum()) if column in onchain.columns else 0
        print(f" - {column} points: {count}")


def _backfill_btc_price_only() -> None:
    cfg = load_runtime_config()
    stats = refresh_btc_daily_from_binance(cfg)
    print(
        "BTC daily store updated: "
        f"{stats['path']} | rows_before={stats['rows_before']} | rows_after={stats['rows_after']} | "
        f"rows_added={stats['rows_added']} | "
        f"last_before={stats['last_date_before']} | last_after={stats['last_date_after']}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill local stores and/or outputs.")
    parser.add_argument(
        "--target",
        choices=["full", "btc-price", "total-market", "social", "onchain"],
        default="full",
        help="What to backfill: full pipeline outputs or a specific source store.",
    )
    args = parser.parse_args()

    if args.target == "full":
        _backfill_full()
    elif args.target == "btc-price":
        _backfill_btc_price_only()
    elif args.target == "total-market":
        _backfill_total_market_only()
    elif args.target == "social":
        _backfill_social_only()
    elif args.target == "onchain":
        _backfill_onchain_only()
