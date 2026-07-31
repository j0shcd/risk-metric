from __future__ import annotations

import pandas as pd


def build_onchain_features(onchain_frame: pd.DataFrame) -> pd.DataFrame:
    frame = pd.DataFrame(index=onchain_frame.index)
    frame["mvrv_ratio_z_proxy"] = onchain_frame.get("mvrv_ratio_z_proxy")
    frame["puell_multiple"] = onchain_frame.get("puell_multiple")
    return frame
