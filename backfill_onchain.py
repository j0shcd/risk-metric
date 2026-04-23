from __future__ import annotations

import pandas as pd

from risk_engine.config import load_runtime_config
from risk_engine.sources.market import load_btc_price
from risk_engine.sources.onchain import load_onchain_metrics


if __name__ == "__main__":
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

    for column in ["mvrv_z_score", "puell_multiple", "supply_in_profit", "supply_in_loss"]:
        count = int(onchain[column].notna().sum()) if column in onchain.columns else 0
        print(f" - {column} points: {count}")
