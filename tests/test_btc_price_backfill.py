import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from risk_engine.config import RuntimeConfig
from risk_engine.sources.btc_price_backfill import refresh_btc_daily_from_binance


def _kline(open_time_ms: int, open_px: float, high_px: float, low_px: float, close_px: float, volume: float) -> list:
    return [
        open_time_ms,
        f"{open_px}",
        f"{high_px}",
        f"{low_px}",
        f"{close_px}",
        f"{volume}",
        open_time_ms + 1,
        "0",
        0,
        "0",
        "0",
        "0",
    ]


class BtcPriceBackfillTests(unittest.TestCase):
    def _cfg(self, root: Path) -> RuntimeConfig:
        return RuntimeConfig(
            project_root=root,
            data_dir=root / "data",
            output_dir=root / "output",
            cache_dir=root / "data",
        )

    @patch("risk_engine.sources.btc_price_backfill._fetch_binance_klines_page")
    def test_refresh_appends_missing_daily_rows(self, mocked_fetch) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "data").mkdir(parents=True, exist_ok=True)

            csv_path = root / "data" / "btc_daily.csv"
            pd.DataFrame(
                {
                    "Date": ["2024-01-01", "2024-01-02"],
                    "Open": [42000.0, 42100.0],
                    "High": [43000.0, 43200.0],
                    "Low": [41000.0, 42000.0],
                    "Price": [42500.0, 42900.0],
                    "Vol.": [1000000.0, 1100000.0],
                    "Change %": [1.19, 1.90],
                }
            ).to_csv(csv_path, index=False)

            mocked_fetch.side_effect = [
                [
                    _kline(1704240000000, 43000.0, 44000.0, 42500.0, 43800.0, 1200000.0),  # 2024-01-03
                    _kline(1704326400000, 43800.0, 44500.0, 43500.0, 44200.0, 1300000.0),  # 2024-01-04
                ],
                [],
            ]

            with patch("risk_engine.sources.btc_price_backfill._yesterday_utc", return_value=pd.Timestamp("2024-01-05")):
                stats = refresh_btc_daily_from_binance(self._cfg(root))

            updated = pd.read_csv(csv_path)
            self.assertEqual(len(updated), 4)
            self.assertIn("2024-01-03", updated["Date"].tolist())
            self.assertIn("2024-01-04", updated["Date"].tolist())
            self.assertEqual(stats["rows_added"], 2)
            self.assertEqual(stats["fetch_mode"], "binance")

    @patch("risk_engine.sources.btc_price_backfill.requests.get")
    def test_refresh_bootstraps_when_btc_daily_missing(self, mocked_get) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "data").mkdir(parents=True, exist_ok=True)

            mocked_response = mocked_get.return_value
            mocked_response.raise_for_status.return_value = None
            mocked_response.json.return_value = {
                "prices": [
                    [1704067200000, 42000.0],  # 2024-01-01
                    [1704153600000, 43000.0],  # 2024-01-02
                ],
                "total_volumes": [
                    [1704067200000, 1000000000.0],
                    [1704153600000, 1100000000.0],
                ],
            }

            stats = refresh_btc_daily_from_binance(self._cfg(root))

            csv_path = root / "data" / "btc_daily.csv"
            self.assertTrue(csv_path.exists())
            updated = pd.read_csv(csv_path)
            self.assertEqual(len(updated), 2)
            self.assertEqual(stats["rows_before"], 0)
            self.assertEqual(stats["rows_after"], 2)
            self.assertEqual(stats["rows_added"], 2)

    @patch("risk_engine.sources.btc_price_backfill.requests.get")
    @patch("risk_engine.sources.btc_price_backfill._fetch_binance_klines_page")
    def test_refresh_falls_back_to_coingecko_when_binance_empty(self, mocked_fetch, mocked_get) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "data").mkdir(parents=True, exist_ok=True)

            csv_path = root / "data" / "btc_daily.csv"
            pd.DataFrame(
                {
                    "Date": ["2024-01-01", "2024-01-02"],
                    "Open": [42000.0, 42100.0],
                    "High": [43000.0, 43200.0],
                    "Low": [41000.0, 42000.0],
                    "Price": [42500.0, 42900.0],
                    "Vol.": [1000000.0, 1100000.0],
                    "Change %": [1.19, 1.90],
                }
            ).to_csv(csv_path, index=False)

            mocked_fetch.return_value = []

            mocked_response = mocked_get.return_value
            mocked_response.raise_for_status.return_value = None
            mocked_response.json.return_value = {
                "prices": [
                    [1704067200000, 42500.0],  # 2024-01-01
                    [1704153600000, 42900.0],  # 2024-01-02
                    [1704240000000, 43800.0],  # 2024-01-03
                    [1704326400000, 44200.0],  # 2024-01-04
                ],
                "total_volumes": [
                    [1704240000000, 1200000.0],
                    [1704326400000, 1300000.0],
                ],
            }

            with patch("risk_engine.sources.btc_price_backfill._yesterday_utc", return_value=pd.Timestamp("2024-01-05")):
                stats = refresh_btc_daily_from_binance(self._cfg(root))

            updated = pd.read_csv(csv_path)
            self.assertEqual(len(updated), 4)
            self.assertIn("2024-01-03", updated["Date"].tolist())
            self.assertIn("2024-01-04", updated["Date"].tolist())
            self.assertEqual(stats["rows_added"], 2)
            self.assertEqual(stats["fetch_mode"], "coingecko_fallback")


if __name__ == "__main__":
    unittest.main()
