import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from risk_engine.config import RuntimeConfig
from risk_engine.sources.onchain import load_onchain_metrics


class OnchainSourceTests(unittest.TestCase):
    def _cfg(self, root: Path) -> RuntimeConfig:
        return RuntimeConfig(
            project_root=root,
            data_dir=root / "data",
            output_dir=root / "output",
            cache_dir=root / "data",
            onchain_fallback_csv=root / "data" / "onchain_metrics.csv",
            glassnode_api_key="test-key",
            enable_paid_sources=True,
        )

    @patch("risk_engine.sources.onchain.safe_get_json")
    def test_fetch_and_persist_onchain_metrics(self, mocked_get) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "data").mkdir(parents=True, exist_ok=True)

            def side_effect(url, timeout_seconds, params=None, headers=None):
                if url.endswith("market/mvrv_z_score"):
                    return [{"t": 1704067200, "v": 1.2}, {"t": 1704153600, "v": 1.3}]
                if url.endswith("indicators/puell_multiple"):
                    return [{"t": 1704067200, "v": 0.9}, {"t": 1704153600, "v": 1.0}]
                if url.endswith("supply/profit_relative"):
                    return [{"t": 1704067200, "v": 0.7}, {"t": 1704153600, "v": 0.72}]
                return None

            mocked_get.side_effect = side_effect

            cfg = self._cfg(root)
            index = pd.date_range("2024-01-01", periods=5, freq="D")
            frame = load_onchain_metrics(cfg, index=index)

            self.assertEqual(float(frame.loc[pd.Timestamp("2024-01-01"), "mvrv_z_score"]), 1.2)
            self.assertEqual(float(frame.loc[pd.Timestamp("2024-01-02"), "puell_multiple"]), 1.0)
            self.assertEqual(float(frame.loc[pd.Timestamp("2024-01-02"), "supply_in_loss"]), 0.28)

            stored = pd.read_csv(root / "data" / "onchain_metrics.csv")
            self.assertEqual(len(stored), 2)
            self.assertIn("mvrv_z_score", stored.columns)
            self.assertIn("puell_multiple", stored.columns)
            self.assertIn("supply_in_profit", stored.columns)

    @patch("risk_engine.sources.onchain.safe_get_json")
    def test_existing_store_preserved_when_fetch_unavailable(self, mocked_get) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "data").mkdir(parents=True, exist_ok=True)

            pd.DataFrame(
                {
                    "Date": ["2024-01-01", "2024-01-02"],
                    "mvrv_z_score": [1.1, 1.2],
                    "puell_multiple": [0.8, 0.9],
                    "supply_in_profit": [0.6, 0.61],
                }
            ).to_csv(root / "data" / "onchain_metrics.csv", index=False)

            mocked_get.return_value = None

            cfg = self._cfg(root)
            index = pd.date_range("2024-01-01", periods=3, freq="D")
            frame = load_onchain_metrics(cfg, index=index)

            self.assertEqual(float(frame.loc[pd.Timestamp("2024-01-02"), "mvrv_z_score"]), 1.2)
            stored = pd.read_csv(root / "data" / "onchain_metrics.csv")
            self.assertEqual(len(stored), 2)


if __name__ == "__main__":
    unittest.main()
