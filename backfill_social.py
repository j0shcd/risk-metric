from __future__ import annotations

from risk_engine.config import load_runtime_config
from risk_engine.sources.market import load_btc_price
from risk_engine.sources.social import load_social_metrics


if __name__ == "__main__":
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
