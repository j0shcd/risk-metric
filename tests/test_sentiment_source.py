import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from risk_engine.config import RuntimeConfig
from risk_engine.sources.sentiment import load_fear_greed_index


class SentimentSourceTests(unittest.TestCase):
    def _cfg(self, root: Path, refresh: bool = True) -> RuntimeConfig:
        return RuntimeConfig(
            project_root=root,
            data_dir=root / "data",
            output_dir=root / "output",
            cache_dir=root / "data",
            refresh_api_sources=refresh,
        )

    @patch("risk_engine.sources.sentiment.safe_get_json")
    def test_load_fear_greed_parses_and_writes_cache(self, mocked_get) -> None:
        mocked_get.return_value = {
            "data": [
                {"timestamp": "1714003200", "value": "62"},
                {"timestamp": "1714003200", "value": "63"},
            ]
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = self._cfg(root)
            cfg.cache_dir.mkdir(parents=True, exist_ok=True)
            idx = pd.date_range("2024-04-24", periods=3, freq="D")
            out = load_fear_greed_index(cfg, idx)

            self.assertEqual(out.attrs.get("source_mode"), "alternative_me_api")
            self.assertFalse(out.dropna().empty)
            cache_path = cfg.cache_dir / "fear_greed_index.csv"
            self.assertTrue(cache_path.exists())

    @patch("risk_engine.sources.sentiment.safe_get_json")
    def test_load_fear_greed_uses_local_cache_when_api_unavailable(self, mocked_get) -> None:
        mocked_get.return_value = None

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = self._cfg(root)
            cache_path = cfg.cache_dir / "fear_greed_index.csv"
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(
                {"Date": ["2024-01-01", "2024-01-02"], "fear_greed_index": [40.0, 45.0]}
            ).to_csv(cache_path, index=False)

            idx = pd.date_range("2024-01-01", periods=3, freq="D")
            out = load_fear_greed_index(cfg, idx)

            self.assertEqual(out.attrs.get("source_mode"), "local_cache")
            self.assertEqual(int(out.notna().sum()), 2)

    @patch("risk_engine.sources.sentiment.safe_get_json")
    def test_load_fear_greed_unavailable_when_no_api_and_no_cache(self, mocked_get) -> None:
        mocked_get.return_value = None

        with tempfile.TemporaryDirectory() as tmp:
            cfg = self._cfg(Path(tmp))
            idx = pd.date_range("2024-01-01", periods=3, freq="D")
            out = load_fear_greed_index(cfg, idx)

            self.assertEqual(out.attrs.get("source_mode"), "unavailable")
            self.assertTrue(out.isna().all())


if __name__ == "__main__":
    unittest.main()
