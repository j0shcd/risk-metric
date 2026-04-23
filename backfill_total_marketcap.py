from __future__ import annotations

import pandas as pd

from risk_engine.config import load_runtime_config
from risk_engine.sources.market import load_btc_price, load_total_market_cap


if __name__ == "__main__":
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
