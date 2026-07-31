import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from risk_engine.config import RuntimeConfig
from risk_engine.sources.cycle import load_cycle_market_context


class CycleSourceTests(unittest.TestCase):
    def _cfg(self, root: Path) -> RuntimeConfig:
        return RuntimeConfig(
            project_root=root,
            data_dir=root / "data",
            output_dir=root / "output",
            cache_dir=root / "data",
            coingecko_btc_market_csv=root / "data" / "btc_market_coingecko.csv",
            wikipedia_pageviews_csv=root / "data" / "wikipedia_pageviews_btc.csv",
            reddit_posts_csv=root / "data" / "reddit_post_volume.csv",
            fred_dxy_csv=root / "data" / "fred_dxy.csv",
            fred_real_yield_csv=root / "data" / "fred_real_yield_10y.csv",
            fred_walcl_csv=root / "data" / "fred_walcl.csv",
            fred_rrp_csv=root / "data" / "fred_rrpontsyd.csv",
            reddit_subreddits=["Bitcoin"],
        )

    @patch("risk_engine.sources.cycle.safe_get_text")
    @patch("risk_engine.sources.cycle.safe_get_json")
    def test_cycle_context_loads_and_labels_source_modes(self, mocked_get_json, mocked_get_text) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "data").mkdir(parents=True, exist_ok=True)

            pd.DataFrame(
                {
                    "Date": ["2024-01-01", "2024-01-02", "2024-01-03"],
                    "Open": [1, 1, 1],
                    "High": [1, 1, 1],
                    "Low": [1, 1, 1],
                    "Price": [42000.0, 43000.0, 44000.0],
                    "Vol.": ["1.2B", "1.3B", "1.1B"],
                    "Change %": [0, 0, 0],
                }
            ).to_csv(root / "data" / "btc_daily.csv", index=False)

            def json_side_effect(url, timeout_seconds, params=None, headers=None):
                if "coingecko" in url:
                    return {
                        "prices": [
                            [1704067200000, 42000.0],
                            [1704153600000, 43000.0],
                            [1704240000000, 44000.0],
                        ],
                        "market_caps": [[1704067200000, 8.0e11]],
                        "total_volumes": [
                            [1704067200000, 2.1e10],
                            [1704153600000, 2.2e10],
                            [1704240000000, 2.3e10],
                        ],
                    }
                if "wikimedia.org" in url:
                    return {
                        "items": [
                            {"timestamp": "2024010100", "views": 120000},
                            {"timestamp": "2024010200", "views": 130000},
                        ]
                    }
                if "pushshift.io" in url:
                    return {
                        "aggs": {
                            "created_utc": [
                                {"key": 1704067200, "doc_count": 700},
                                {"key": 1704153600, "doc_count": 720},
                            ]
                        }
                    }
                return None

            def text_side_effect(url, timeout_seconds, params=None, headers=None):
                fred_id = str(params.get("id")) if params else ""
                if fred_id == "DTWEXBGS":
                    return "DATE,DTWEXBGS\n2024-01-01,101.0\n2024-01-02,100.5\n"
                if fred_id == "DFII10":
                    return "DATE,DFII10\n2024-01-01,1.3\n2024-01-02,1.2\n"
                if fred_id == "WALCL":
                    return "DATE,WALCL\n2024-01-01,8000000\n2024-01-02,8050000\n"
                if fred_id == "RRPONTSYD":
                    return "DATE,RRPONTSYD\n2024-01-01,1500\n2024-01-02,1490\n"
                return None

            mocked_get_json.side_effect = json_side_effect
            mocked_get_text.side_effect = text_side_effect

            index = pd.date_range("2024-01-01", periods=4, freq="D")
            btc_price = pd.Series([42000.0, 43000.0, 44000.0, 45000.0], index=index)
            social = pd.DataFrame({"google_trends_interest": [40.0, 42.0, 41.0, 43.0]}, index=index)
            social.attrs["source_modes"] = {"google_trends_interest": "local_cache"}

            context = load_cycle_market_context(self._cfg(root), index=index, btc_price=btc_price, social_frame=social)

            self.assertIn("btc_volume_usd", context.columns)
            self.assertIn("wikipedia_pageviews", context.columns)
            self.assertIn("reddit_post_volume", context.columns)
            self.assertIn("net_liquidity", context.columns)
            self.assertEqual(context.attrs["source_modes"]["cycle::btc_volume_usd"], "coingecko_free_api")
            self.assertEqual(context.attrs["source_modes"]["cycle::wikipedia_pageviews"], "wikimedia_api")
            self.assertEqual(context.attrs["source_modes"]["cycle::dxy"], "fred_graph_csv")
            self.assertEqual(float(context.loc[pd.Timestamp("2024-01-01"), "net_liquidity"]), 6500000.0)

    @patch("risk_engine.sources.cycle.safe_get_text")
    @patch("risk_engine.sources.cycle.safe_get_json")
    def test_cycle_context_uses_fred_json_api_when_key_present(self, mocked_get_json, mocked_get_text) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "data").mkdir(parents=True, exist_ok=True)

            pd.DataFrame(
                {
                    "Date": ["2024-01-01", "2024-01-02"],
                    "Open": [1, 1],
                    "High": [1, 1],
                    "Low": [1, 1],
                    "Price": [42000.0, 43000.0],
                    "Vol.": ["1.0B", "1.1B"],
                    "Change %": [0, 0],
                }
            ).to_csv(root / "data" / "btc_daily.csv", index=False)

            def json_side_effect(url, timeout_seconds, params=None, headers=None):
                if "coingecko" in url:
                    return {"prices": [], "market_caps": [], "total_volumes": []}
                if "wikimedia.org" in url:
                    return {"items": []}
                if "pushshift.io" in url:
                    return {"aggs": {"created_utc": []}}
                if "api.stlouisfed.org" in url:
                    series_id = str((params or {}).get("series_id"))
                    values = {
                        "DTWEXBGS": "101.2",
                        "DFII10": "1.1",
                        "WALCL": "8100000",
                        "RRPONTSYD": "1480",
                    }
                    return {
                        "observations": [
                            {"date": "2024-01-01", "value": values.get(series_id, ".")},
                            {"date": "2024-01-02", "value": values.get(series_id, ".")},
                        ]
                    }
                return None

            mocked_get_json.side_effect = json_side_effect
            mocked_get_text.return_value = None

            index = pd.date_range("2024-01-01", periods=2, freq="D")
            btc_price = pd.Series([42000.0, 43000.0], index=index)
            social = pd.DataFrame({"google_trends_interest": [40.0, 42.0]}, index=index)
            social.attrs["source_modes"] = {"google_trends_interest": "local_cache"}

            cfg = replace(self._cfg(root), fred_api_key="fred-key")
            context = load_cycle_market_context(cfg, index=index, btc_price=btc_price, social_frame=social)

            self.assertEqual(context.attrs["source_modes"]["cycle::dxy"], "fred_api_json")
            self.assertEqual(context.attrs["source_modes"]["cycle::net_liquidity"], "derived_from_fred_api_json")
            self.assertEqual(float(context.loc[pd.Timestamp("2024-01-01"), "net_liquidity"]), 6620000.0)

    @patch("risk_engine.sources.cycle.safe_get_text")
    @patch("risk_engine.sources.cycle.safe_get_json")
    def test_cycle_cache_only_mode_skips_api_calls(self, mocked_get_json, mocked_get_text) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "data").mkdir(parents=True, exist_ok=True)

            pd.DataFrame(
                {
                    "Date": ["2024-01-01", "2024-01-02"],
                    "Open": [1, 1],
                    "High": [1, 1],
                    "Low": [1, 1],
                    "Price": [42000.0, 43000.0],
                    "Vol.": ["1.0B", "1.1B"],
                    "Change %": [0, 0],
                }
            ).to_csv(root / "data" / "btc_daily.csv", index=False)

            pd.DataFrame({"Date": ["2024-01-01"], "dxy": [101.0]}).to_csv(root / "data" / "fred_dxy.csv", index=False)
            pd.DataFrame({"Date": ["2024-01-01"], "real_yield_10y": [1.1]}).to_csv(
                root / "data" / "fred_real_yield_10y.csv",
                index=False,
            )
            pd.DataFrame({"Date": ["2024-01-01"], "fed_balance_sheet": [8100000]}).to_csv(
                root / "data" / "fred_walcl.csv",
                index=False,
            )
            pd.DataFrame({"Date": ["2024-01-01"], "reverse_repo_balance": [1480000]}).to_csv(
                root / "data" / "fred_rrpontsyd.csv",
                index=False,
            )

            index = pd.date_range("2024-01-01", periods=2, freq="D")
            btc_price = pd.Series([42000.0, 43000.0], index=index)
            social = pd.DataFrame({"google_trends_interest": [40.0, 42.0]}, index=index)
            social.attrs["source_modes"] = {"google_trends_interest": "local_cache"}

            cfg = replace(self._cfg(root), refresh_api_sources=False)
            context = load_cycle_market_context(cfg, index=index, btc_price=btc_price, social_frame=social)

            self.assertEqual(context.attrs["source_modes"]["cycle::dxy"], "local_cache")
            mocked_get_json.assert_not_called()
            mocked_get_text.assert_not_called()

    @patch("risk_engine.sources.cycle.safe_get_text")
    @patch("risk_engine.sources.cycle.safe_get_json")
    def test_wikimedia_request_uses_user_agent_and_optional_token(self, mocked_get_json, mocked_get_text) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "data").mkdir(parents=True, exist_ok=True)

            pd.DataFrame(
                {
                    "Date": ["2024-01-01", "2024-01-02"],
                    "Open": [1, 1],
                    "High": [1, 1],
                    "Low": [1, 1],
                    "Price": [42000.0, 43000.0],
                    "Vol.": ["1.0B", "1.1B"],
                    "Change %": [0, 0],
                }
            ).to_csv(root / "data" / "btc_daily.csv", index=False)

            def json_side_effect(url, timeout_seconds, params=None, headers=None):
                if "wikimedia.org" in url:
                    self.assertIn("User-Agent", headers or {})
                    self.assertIn("Api-User-Agent", headers or {})
                    self.assertEqual((headers or {}).get("Authorization"), "Bearer wiki-token")
                    return {"items": []}
                if "coingecko" in url:
                    return {"prices": [], "market_caps": [], "total_volumes": []}
                if "pushshift.io" in url:
                    return {"aggs": {"created_utc": []}}
                if "api.stlouisfed.org" in url:
                    return {"observations": []}
                return None

            mocked_get_json.side_effect = json_side_effect
            mocked_get_text.return_value = None

            index = pd.date_range("2024-01-01", periods=2, freq="D")
            btc_price = pd.Series([42000.0, 43000.0], index=index)
            social = pd.DataFrame({"google_trends_interest": [40.0, 42.0]}, index=index)
            social.attrs["source_modes"] = {"google_trends_interest": "local_cache"}

            cfg = replace(
                self._cfg(root),
                wikimedia_api_token="wiki-token",
                wikimedia_api_user_agent="risk-metric-test/1.0 (test@example.com)",
            )
            load_cycle_market_context(cfg, index=index, btc_price=btc_price, social_frame=social)


if __name__ == "__main__":
    unittest.main()
