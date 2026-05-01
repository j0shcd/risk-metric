import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
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
            refresh_api_sources=True,
        )

    @patch("risk_engine.sources.onchain.requests.get")
    def test_fetch_and_persist_onchain_metrics(self, mocked_get) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "data").mkdir(parents=True, exist_ok=True)

            class _Resp:
                def __init__(self, payload):
                    self._payload = payload

                def raise_for_status(self) -> None:
                    return None

                def json(self):
                    return self._payload

            dates = pd.date_range("2023-01-01", periods=420, freq="D")
            rows = []
            for i, dt in enumerate(dates):
                rows.append(
                    {
                        "asset": "btc",
                        "time": dt.strftime("%Y-%m-%dT00:00:00.000000000Z"),
                        "CapMVRVCur": str(0.8 + 0.002 * i + 0.04 * np.sin(i / 16.0)),
                        "IssTotUSD": str(100_000_000 + 2_000_000 * np.sin(i / 22.0)),
                    }
                )
            mocked_get.return_value = _Resp({"data": rows})

            cfg = self._cfg(root)
            index = pd.date_range("2023-01-01", periods=420, freq="D")
            frame = load_onchain_metrics(cfg, index=index)

            self.assertGreater(int(frame["mvrv_z_score"].notna().sum()), 0)
            self.assertGreater(int(frame["puell_multiple"].notna().sum()), 0)
            self.assertGreater(int(frame["supply_in_profit"].notna().sum()), 0)
            self.assertTrue(((frame["supply_in_loss"] >= 0.0) & (frame["supply_in_loss"] <= 1.0)).dropna().all())

            stored = pd.read_csv(root / "data" / "onchain_metrics.csv")
            self.assertGreaterEqual(len(stored), 400)
            self.assertIn("mvrv_z_score", stored.columns)
            self.assertIn("puell_multiple", stored.columns)
            self.assertIn("supply_in_profit", stored.columns)

    @patch("risk_engine.sources.onchain.requests.get")
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

            mocked_get.side_effect = RuntimeError("network unavailable")

            cfg = self._cfg(root)
            index = pd.date_range("2024-01-01", periods=3, freq="D")
            frame = load_onchain_metrics(cfg, index=index)

            self.assertEqual(float(frame.loc[pd.Timestamp("2024-01-02"), "mvrv_z_score"]), 1.2)
            stored = pd.read_csv(root / "data" / "onchain_metrics.csv")
            self.assertEqual(len(stored), 2)


if __name__ == "__main__":
    unittest.main()
