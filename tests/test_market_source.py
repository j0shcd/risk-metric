import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from risk_engine.config import RuntimeConfig
from risk_engine.sources.market import load_total_market_cap


class MarketSourceTests(unittest.TestCase):
    def _cfg(self, root: Path) -> RuntimeConfig:
        return RuntimeConfig(
            project_root=root,
            data_dir=root / "data",
            output_dir=root / "output",
            cache_dir=root / "data",
            total_marketcap_csv=root / "data" / "total_marketcap.csv",
        )

    @patch("risk_engine.sources.market.safe_get_json")
    def test_free_latest_snapshot_appends_to_local_csv(self, mocked_get) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "data").mkdir(parents=True, exist_ok=True)

            csv_path = root / "data" / "total_marketcap.csv"
            pd.DataFrame(
                {
                    "Date": ["2024-01-01", "2024-01-02"],
                    "total_market_cap": [1.0e12, 1.1e12],
                }
            ).to_csv(csv_path, index=False)

            mocked_get.return_value = {
                "data": {
                    "updated_at": 1704240000,  # 2024-01-03 00:00:00 UTC
                    "total_market_cap": {"usd": 1.2e12},
                }
            }

            index = pd.date_range("2024-01-01", periods=4, freq="D")
            series = load_total_market_cap(self._cfg(root), index=index)

            self.assertEqual(float(series.loc[pd.Timestamp("2024-01-03")]), 1.2e12)

            updated = pd.read_csv(csv_path)
            self.assertEqual(len(updated), 3)
            self.assertIn("2024-01-03", updated["Date"].tolist())

    @patch("risk_engine.sources.market.safe_get_json")
    def test_free_latest_snapshot_overwrites_same_day_value(self, mocked_get) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "data").mkdir(parents=True, exist_ok=True)

            csv_path = root / "data" / "total_marketcap.csv"
            pd.DataFrame(
                {
                    "Date": ["2024-01-03"],
                    "total_market_cap": [1.0e12],
                }
            ).to_csv(csv_path, index=False)

            mocked_get.return_value = {
                "data": {
                    "updated_at": 1704240000,  # 2024-01-03 00:00:00 UTC
                    "total_market_cap": {"usd": 1.3e12},
                }
            }

            index = pd.date_range("2024-01-01", periods=4, freq="D")
            _ = load_total_market_cap(self._cfg(root), index=index)

            updated = pd.read_csv(csv_path)
            self.assertEqual(len(updated), 1)
            self.assertEqual(float(updated.loc[0, "total_market_cap"]), 1.3e12)


if __name__ == "__main__":
    unittest.main()
