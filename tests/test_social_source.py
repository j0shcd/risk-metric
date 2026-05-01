import tempfile
import unittest
from dataclasses import replace
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
            youtube_channel_ids=["UC1234567890123456789012"] if youtube_key else [],
            google_trends_api_key=trends_key,
            google_trends_api_url="https://trends.googleapis.com/google-trends" if trends_key else None,
            google_trends_terms=["bitcoin"] if trends_key else [],
            enable_google_trends_source=bool(trends_key),
            youtube_fallback_csv=root / "data" / "youtube_interest.csv",
            google_trends_csv=root / "data" / "google_trends_interest.csv",
            coinbase_rank_csv=root / "data" / "coinbase_app_rank.csv",
            apple_app_store_country="us",
            coinbase_ios_app_id="886427730",
            enable_optional_social_sources=True,
            enable_coinbase_app_rank=True,
            youtube_min_fetch_interval_hours=24,
            youtube_max_handle_resolutions_per_run=2,
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
    def test_youtube_handle_resolution_uses_forhandle(self, mocked_get) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "data").mkdir(parents=True, exist_ok=True)

            def side_effect(url, timeout_seconds, headers=None, params=None):
                if "googleapis" not in url:
                    return None
                if params and "forHandle" in params:
                    return {"items": [{"id": "UCabcdefghijABCDEFGHIJ12"}]}
                if params and "id" in params and params.get("part") == "statistics":
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
            cfg = replace(cfg, youtube_channel_ids=["@intothecryptoverse"], enable_coinbase_app_rank=False)
            index = pd.date_range("2026-04-01", periods=10, freq="D")
            social = load_social_metrics(cfg, index=index)

            self.assertEqual(social.attrs.get("source_modes", {}).get("youtube_interest"), "youtube_api")
            stored = pd.read_csv(root / "data" / "youtube_interest.csv")
            self.assertGreaterEqual(len(stored), 1)

            calls = mocked_get.call_args_list
            self.assertTrue(any("forHandle" in (call.kwargs.get("params") or {}) for call in calls))

    @patch("risk_engine.sources.social.safe_get_json")
    def test_youtube_skips_fetch_with_fresh_snapshot(self, mocked_get) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "data").mkdir(parents=True, exist_ok=True)

            today = pd.Timestamp.now("UTC").tz_localize(None).normalize().strftime("%Y-%m-%d")
            pd.DataFrame(
                {
                    "Date": [today],
                    "youtube_interest": [12.0],
                }
            ).to_csv(root / "data" / "youtube_interest.csv", index=False)

            cfg = self._cfg(root, youtube_key="abc")
            cfg = replace(cfg, enable_coinbase_app_rank=False)
            index = pd.date_range("2026-04-20", periods=15, freq="D")
            social = load_social_metrics(cfg, index=index)

            self.assertEqual(float(social["youtube_interest"].dropna().iloc[-1]), 12.0)
            mocked_get.assert_not_called()

    @patch("risk_engine.sources.social.safe_get_json")
    def test_social_cache_only_mode_skips_api_calls(self, mocked_get) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "data").mkdir(parents=True, exist_ok=True)

            pd.DataFrame(
                {
                    "Date": ["2026-04-20"],
                    "youtube_interest": [10.0],
                }
            ).to_csv(root / "data" / "youtube_interest.csv", index=False)

            cfg = self._cfg(root, youtube_key="abc")
            cfg = replace(cfg, refresh_api_sources=False, enable_coinbase_app_rank=False)
            index = pd.date_range("2026-04-20", periods=3, freq="D")
            social = load_social_metrics(cfg, index=index)

            self.assertEqual(float(social.loc[pd.Timestamp("2026-04-20"), "youtube_interest"]), 10.0)
            mocked_get.assert_not_called()

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
    def test_google_trends_disallowed_url_skips_fetch(self, mocked_get) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "data").mkdir(parents=True, exist_ok=True)

            cfg = self._cfg(root, youtube_key=None, trends_key="gt-key")
            cfg = replace(cfg, google_trends_api_url="https://example.com/google-trends", enable_coinbase_app_rank=False)
            index = pd.date_range("2026-04-20", periods=5, freq="D")
            social = load_social_metrics(cfg, index=index)

            self.assertTrue(social["google_trends_interest"].isna().all())
            mocked_get.assert_not_called()

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
