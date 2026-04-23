from __future__ import annotations

import pandas as pd


def build_onchain_features(onchain_frame: pd.DataFrame) -> pd.DataFrame:
    frame = pd.DataFrame(index=onchain_frame.index)
    frame["mvrv_z_score"] = onchain_frame.get("mvrv_z_score")
    frame["puell_multiple"] = onchain_frame.get("puell_multiple")
    frame["supply_in_profit"] = onchain_frame.get("supply_in_profit")
    frame["supply_in_loss"] = onchain_frame.get("supply_in_loss")
    return frame
