import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from risk_engine.config import RuntimeConfig
from risk_engine.sources.social import load_social_metrics


class SocialSourceTests(unittest.TestCase):
    def _cfg(
        self,
        root: Path,
        youtube_key: str | None = None,
        trends_key: str | None = None,
    ) -> RuntimeConfig:
        return RuntimeConfig(
            project_root=root,
            data_dir=root / "data",
            output_dir=root / "output",
            cache_dir=root / "data",
            youtube_api_key=youtube_key,
            youtube_channel_ids=["ch1"] if youtube_key else [],
            google_trends_api_key=trends_key,
            google_trends_api_url="https://example.com/google-trends" if trends_key else None,
            google_trends_terms=["bitcoin"] if trends_key else [],
            youtube_fallback_csv=root / "data" / "youtube_interest.csv",
            google_trends_csv=root / "data" / "google_trends_interest.csv",
            coinbase_rank_csv=root / "data" / "coinbase_app_rank.csv",
            apple_app_store_country="us",
            coinbase_ios_app_id="886427730",
            enable_optional_social_sources=True,
            enable_coinbase_app_rank=True,
        )

    @patch("risk_engine.sources.social.safe_get_json")
    def test_youtube_snapshot_persists_history(self, mocked_get) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "data").mkdir(parents=True, exist_ok=True)

            pd.DataFrame(
                {
                    "Date": ["2024-01-01"],
                    "youtube_interest": [1.0],
                }
            ).to_csv(root / "data" / "youtube_interest.csv", index=False)

            def side_effect(url, timeout_seconds, headers=None, params=None):
                if "googleapis" in url:
                    return {
                        "items": [
                            {
                                "statistics": {
                                    "subscriberCount": "1000",
                                    "viewCount": "50000",
                                }
                            }
                        ]
                    }
                return None

            mocked_get.side_effect = side_effect

            cfg = self._cfg(root, youtube_key="abc")
            index = pd.date_range("2024-01-01", periods=1200, freq="D")
            social = load_social_metrics(cfg, index=index)

            self.assertGreater(int(social["youtube_interest"].notna().sum()), 1)

            stored = pd.read_csv(root / "data" / "youtube_interest.csv")
            self.assertGreaterEqual(len(stored), 2)

    @patch("risk_engine.sources.social.safe_get_json")
    def test_google_trends_fetch_persists_history(self, mocked_get) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "data").mkdir(parents=True, exist_ok=True)

            pd.DataFrame(
                {
                    "Date": ["2026-04-20"],
                    "google_trends_interest": [42.0],
                }
            ).to_csv(root / "data" / "google_trends_interest.csv", index=False)

            def side_effect(url, timeout_seconds, headers=None, params=None):
                if "google-trends" in url:
                    return {
                        "data": [
                            {"date": "2026-04-21", "value": 55},
                            {"date": "2026-04-22", "value": 60},
                        ]
                    }
                return None

            mocked_get.side_effect = side_effect

            cfg = self._cfg(root, youtube_key=None, trends_key="gt-key")
            index = pd.date_range("2026-04-20", periods=5, freq="D")
            social = load_social_metrics(cfg, index=index)

            self.assertEqual(float(social.loc[pd.Timestamp("2026-04-22"), "google_trends_interest"]), 60.0)

            stored = pd.read_csv(root / "data" / "google_trends_interest.csv")
            self.assertGreaterEqual(len(stored), 3)

    @patch("risk_engine.sources.social.safe_get_json")
    def test_coinbase_rank_fetch_persists_and_returns_negative_proxy(self, mocked_get) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "data").mkdir(parents=True, exist_ok=True)

            def side_effect(url, timeout_seconds, headers=None, params=None):
                if "rss.marketingtools.apple.com" in url:
                    return {
                        "feed": {
                            "updated": "2026-04-23T10:00:00Z",
                            "results": [
                                {"id": "123", "name": "Other App"},
                                {"id": "886427730", "name": "Coinbase"},
                            ],
                        }
                    }
                return None

            mocked_get.side_effect = side_effect

            cfg = self._cfg(root, youtube_key=None)
            index = pd.date_range("2026-04-20", periods=7, freq="D")
            social = load_social_metrics(cfg, index=index)

            target_date = pd.Timestamp("2026-04-23")
            self.assertEqual(float(social.loc[target_date, "coinbase_app_rank_proxy"]), -2.0)

            stored = pd.read_csv(root / "data" / "coinbase_app_rank.csv")
            self.assertEqual(float(stored.loc[0, "coinbase_app_rank"]), 2.0)


if __name__ == "__main__":
    unittest.main()
