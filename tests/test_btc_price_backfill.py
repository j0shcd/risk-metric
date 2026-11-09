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

            with patch("risk_engine.sources.btc_price_backfill._yesterday_utc", return_value=pd.Timestamp("2024-01-05")), \
                    patch("risk_engine.sources.btc_price_backfill._fetch_coingecko_daily_range",
                          return_value=pd.DataFrame(columns=["Date", "Price"])):
                stats = refresh_btc_daily_from_binance(self._cfg(root))

            updated = pd.read_csv(csv_path)
            self.assertEqual(len(updated), 4)
            self.assertIn("2024-01-03", updated["Date"].tolist())
            self.assertIn("2024-01-04", updated["Date"].tolist())
            self.assertEqual(stats["rows_added"], 2)
            self.assertEqual(stats["fetch_mode"], "binance")

    @patch("risk_engine.sources.btc_price_backfill.request_json")
    def test_refresh_bootstraps_when_btc_daily_missing(self, mocked_get) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "data").mkdir(parents=True, exist_ok=True)

            mocked_get.return_value = {
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
            self.assertAlmostEqual(float(updated.loc[0, "Vol."]), 1000000000.0 / 42000.0, places=2)
            self.assertAlmostEqual(float(updated.loc[1, "Vol."]), 1100000000.0 / 43000.0, places=2)
            self.assertEqual(stats["rows_before"], 0)
            self.assertEqual(stats["rows_after"], 2)
            self.assertEqual(stats["rows_added"], 2)

    @patch("risk_engine.sources.btc_price_backfill.request_json")
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

            mocked_get.return_value = {
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

    @patch("risk_engine.sources.btc_price_backfill.request_json")
    @patch("risk_engine.sources.btc_price_backfill._fetch_binance_klines_page")
    def test_refresh_fills_remaining_gap_with_coingecko_when_binance_partial(self, mocked_fetch, mocked_get) -> None:
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
                ],
                [],
            ]

            mocked_get.return_value = {
                "prices": [
                    [1704326400000, 44200.0],  # 2024-01-04
                    [1704412800000, 44600.0],  # 2024-01-05
                ],
                "total_volumes": [
                    [1704326400000, 1300000.0],
                    [1704412800000, 1400000.0],
                ],
            }

            with patch("risk_engine.sources.btc_price_backfill._yesterday_utc", return_value=pd.Timestamp("2024-01-06")):
                stats = refresh_btc_daily_from_binance(self._cfg(root))

            updated = pd.read_csv(csv_path)
            self.assertEqual(len(updated), 5)
            self.assertIn("2024-01-03", updated["Date"].tolist())
            self.assertIn("2024-01-04", updated["Date"].tolist())
            self.assertIn("2024-01-05", updated["Date"].tolist())
            self.assertEqual(stats["rows_added"], 3)
            self.assertEqual(stats["fetch_mode"], "binance+coingecko_fallback")


    @patch("risk_engine.sources.btc_price_backfill._fetch_binance_klines_page")
    def test_page_budget_fails_before_overwriting_existing_cache(self, fetch):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "data").mkdir()
            cache = root / "data/btc_daily.csv"
            original = b"Date,Open,High,Low,Price,Vol.,Change %\n2024-01-01,1,1,1,1,1,0\n"
            cache.write_bytes(original)
            # One full response demands another page, exceeding the patched budget.
            fetch.return_value = [_kline(1704153600000, 1, 1, 1, 1, 1)] * 1000
            with patch("risk_engine.sources.btc_price_backfill.MAX_BACKFILL_PAGES", 1), \
                    patch("risk_engine.sources.btc_price_backfill._fetch_coingecko_daily_range",
                          side_effect=AssertionError("budget must stop before fallback")):
                with self.assertRaisesRegex(RuntimeError, "page budget"):
                    refresh_btc_daily_from_binance(self._cfg(root))
            self.assertEqual(cache.read_bytes(), original)
            self.assertEqual(fetch.call_count, 1)

    def test_range_backfill_bounded_before_fetching_or_writing(self):
        from risk_engine.sources.btc_price_backfill import _fetch_coingecko_daily_range
        with patch("risk_engine.sources.btc_price_backfill.request_json", return_value={}) as fetch, \
                patch("risk_engine.sources.btc_price_backfill.MAX_BACKFILL_PAGES", 1):
            with self.assertRaisesRegex(RuntimeError, "page budget"):
                _fetch_coingecko_daily_range(self._cfg(Path("unused")),
                                            pd.Timestamp("2020-01-01"), pd.Timestamp("2021-01-01"))
            self.assertEqual(fetch.call_count, 1)


if __name__ == "__main__":
    unittest.main()
