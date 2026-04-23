from __future__ import annotations

import pandas as pd


def build_social_sentiment_features(
    fear_greed: pd.Series,
    social_frame: pd.DataFrame,
) -> pd.DataFrame:
    frame = pd.DataFrame(index=fear_greed.index)
    frame["fear_greed_index"] = fear_greed
    frame["youtube_interest"] = social_frame.get("youtube_interest")
    frame["google_trends_interest"] = social_frame.get("google_trends_interest")
    frame["coinbase_app_rank_proxy"] = social_frame.get("coinbase_app_rank_proxy")
    return frame
