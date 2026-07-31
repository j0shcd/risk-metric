import unittest

import numpy as np
import pandas as pd

from risk_engine.features.market_features import build_market_features


class MarketFeatureTests(unittest.TestCase):
    def test_historical_features_do_not_change_when_future_rows_are_appended(self) -> None:
        index = pd.date_range("2020-01-01", periods=500, freq="D")
        x = np.arange(len(index), dtype=float)
        btc = pd.Series(np.exp(4.0 + 0.004 * x + 0.15 * np.sin(x / 21.0)), index=index)
        total = pd.Series(np.exp(12.0 + 0.003 * x + 0.08 * np.cos(x / 25.0)), index=index)

        prefix = build_market_features(btc.iloc[:400], total.iloc[:400])
        full_prefix = build_market_features(btc, total).iloc[:400]

        for column in ["btc_log_reg_deviation", "total_log_reg_deviation", "btc_dominance_proxy"]:
            pd.testing.assert_series_equal(prefix[column], full_prefix[column], check_names=False)


if __name__ == "__main__":
    unittest.main()
