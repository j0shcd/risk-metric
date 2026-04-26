import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from risk_engine.config import RuntimeConfig
from risk_engine.pipeline import run_pipeline


class PipelineBehaviorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.index = pd.date_range("2020-01-01", periods=900, freq="D")

        self.btc_price = pd.Series(
            np.linspace(7000.0, 65000.0, len(self.index)) + 1000.0 * np.sin(np.arange(len(self.index)) / 50.0),
            index=self.index,
            name="btc_price",
        )
        self.total_market = pd.Series(
            np.linspace(2e11, 2.5e12, len(self.index)) + 2e10 * np.sin(np.arange(len(self.index)) / 60.0),
            index=self.index,
            name="total_market_cap",
        )

        self.onchain = pd.DataFrame(
            {
                "mvrv_z_score": np.linspace(-1.0, 4.0, len(self.index)),
                "puell_multiple": 1.0 + 0.5 * np.sin(np.arange(len(self.index)) / 45.0),
                "supply_in_profit": np.clip(0.2 + np.linspace(0.0, 0.8, len(self.index)), 0.0, 1.0),
                "supply_in_loss": np.clip(0.8 - np.linspace(0.0, 0.8, len(self.index)), 0.0, 1.0),
            },
            index=self.index,
        )

        self.fear_greed = pd.Series(
            50.0 + 20.0 * np.sin(np.arange(len(self.index)) / 40.0),
            index=self.index,
            name="fear_greed_index",
        )

        self.social = pd.DataFrame(
            {
                "youtube_interest": 10.0 + np.sin(np.arange(len(self.index)) / 25.0),
                "google_trends_interest": 30.0 + 5.0 * np.sin(np.arange(len(self.index)) / 18.0),
                "coinbase_app_rank_proxy": -50.0 + 3.0 * np.sin(np.arange(len(self.index)) / 22.0),
            },
            index=self.index,
        )

        cwd = Path.cwd()
        self.cfg = RuntimeConfig(
            project_root=cwd,
            data_dir=cwd / "data",
            output_dir=cwd / "output",
            cache_dir=cwd / "data",
        )

    @patch("risk_engine.pipeline.load_social_metrics")
    @patch("risk_engine.pipeline.load_fear_greed_index")
    @patch("risk_engine.pipeline.load_onchain_metrics")
    @patch("risk_engine.pipeline.load_total_market_cap")
    @patch("risk_engine.pipeline.load_btc_price")
    def test_pipeline_outputs_required_columns(
        self,
        mocked_btc,
        mocked_total,
        mocked_onchain,
        mocked_fear,
        mocked_social,
    ) -> None:
        mocked_btc.return_value = self.btc_price
        mocked_total.return_value = self.total_market
        mocked_onchain.return_value = self.onchain
        mocked_fear.return_value = self.fear_greed
        mocked_social.return_value = self.social

        result = run_pipeline(self.cfg)
        output = result.series

        for column in [
            "btc_risk_heat",
            "btc_risk_attention",
            "total_market_risk_heat",
            "total_market_risk_attention",
            "headline_attention",
            "headline_heat",
            "confidence_score",
        ]:
            self.assertIn(column, output.columns)
            self.assertFalse(output[column].dropna().empty)

        for bounded_column in [
            "btc_risk_heat",
            "btc_risk_attention",
            "total_market_risk_heat",
            "total_market_risk_attention",
            "headline_attention",
            "headline_heat",
            "confidence_score",
        ]:
            values = output[bounded_column].dropna()
            self.assertTrue(((values >= 0.0) & (values <= 1.0)).all())

        self.assertFalse(result.metric_health.empty)
        self.assertFalse(result.source_health.empty)
        self.assertIn("metric", result.metric_health.columns)
        self.assertIn("source_mode", result.metric_health.columns)
        self.assertIn("reliability_mode_multiplier", result.metric_health.columns)
        self.assertIn("adjusted_base_reliability", result.metric_health.columns)
        self.assertIn("source", result.source_health.columns)
        self.assertIn("btc", result.category_breakdowns)
        self.assertIn("total_market", result.category_breakdowns)
        self.assertFalse(result.category_breakdowns["btc"].empty)
        self.assertIn("effective_weight_total", result.category_breakdowns["btc"].columns)
        self.assertIn("btc", result.metric_breakdowns)
        self.assertIn("total_market", result.metric_breakdowns)
        self.assertFalse(result.metric_breakdowns["btc"].empty)
        self.assertIn("effective_metric_weight_total", result.metric_breakdowns["btc"].columns)
        self.assertIn("btc_price", result.source_modes)
        self.assertIn("total_market_cap", result.source_modes)
        self.assertIn("onchain::mvrv_z_score", result.source_modes)
        self.assertIn("social::youtube_interest", result.source_modes)

    @patch("risk_engine.pipeline.load_social_metrics")
    @patch("risk_engine.pipeline.load_fear_greed_index")
    @patch("risk_engine.pipeline.load_onchain_metrics")
    @patch("risk_engine.pipeline.load_total_market_cap")
    @patch("risk_engine.pipeline.load_btc_price")
    def test_confidence_drops_when_onchain_unavailable(
        self,
        mocked_btc,
        mocked_total,
        mocked_onchain,
        mocked_fear,
        mocked_social,
    ) -> None:
        mocked_btc.return_value = self.btc_price
        mocked_total.return_value = self.total_market
        mocked_fear.return_value = self.fear_greed
        mocked_social.return_value = self.social

        mocked_onchain.return_value = self.onchain
        baseline = run_pipeline(self.cfg).series["confidence_score"].iloc[-1]

        out_onchain = self.onchain.copy()
        out_onchain.loc[:, :] = np.nan
        mocked_onchain.return_value = out_onchain

        degraded = run_pipeline(self.cfg).series["confidence_score"].iloc[-1]

        self.assertLess(degraded, baseline)

    @patch("risk_engine.pipeline.load_social_metrics")
    @patch("risk_engine.pipeline.load_fear_greed_index")
    @patch("risk_engine.pipeline.load_onchain_metrics")
    @patch("risk_engine.pipeline.load_total_market_cap")
    @patch("risk_engine.pipeline.load_btc_price")
    def test_confidence_drops_when_total_market_uses_local_cache_mode(
        self,
        mocked_btc,
        mocked_total,
        mocked_onchain,
        mocked_fear,
        mocked_social,
    ) -> None:
        mocked_btc.return_value = self.btc_price
        mocked_onchain.return_value = self.onchain
        mocked_fear.return_value = self.fear_greed
        mocked_social.return_value = self.social

        total_api = self.total_market.copy()
        total_api.attrs["source_mode"] = "cmc_api"
        mocked_total.return_value = total_api
        baseline = run_pipeline(self.cfg).series["confidence_score"].iloc[-1]

        total_cached = self.total_market.copy()
        total_cached.attrs["source_mode"] = "local_cache"
        mocked_total.return_value = total_cached
        degraded = run_pipeline(self.cfg).series["confidence_score"].iloc[-1]

        self.assertLess(degraded, baseline)

    @patch("risk_engine.pipeline.load_social_metrics")
    @patch("risk_engine.pipeline.load_fear_greed_index")
    @patch("risk_engine.pipeline.load_onchain_metrics")
    @patch("risk_engine.pipeline.load_total_market_cap")
    @patch("risk_engine.pipeline.load_btc_price")
    def test_total_market_fallback_proxies_disabled_when_total_market_coverage_good(
        self,
        mocked_btc,
        mocked_total,
        mocked_onchain,
        mocked_fear,
        mocked_social,
    ) -> None:
        mocked_btc.return_value = self.btc_price
        mocked_total.return_value = self.total_market
        mocked_onchain.return_value = self.onchain
        mocked_fear.return_value = self.fear_greed
        mocked_social.return_value = self.social

        result = run_pipeline(self.cfg)
        metric_health = result.metric_health
        proxy_rows = metric_health[
            (metric_health["category"] == "price_structure")
            & (metric_health["target"] == "total_market")
            & (
                metric_health["metric"].isin(
                    [
                        "btc_trend_extension_50d_350d",
                        "btc_running_roi_1y",
                        "btc_log_reg_deviation",
                    ]
                )
            )
        ]
        self.assertTrue(proxy_rows.empty)

    @patch("risk_engine.pipeline.load_social_metrics")
    @patch("risk_engine.pipeline.load_fear_greed_index")
    @patch("risk_engine.pipeline.load_onchain_metrics")
    @patch("risk_engine.pipeline.load_total_market_cap")
    @patch("risk_engine.pipeline.load_btc_price")
    def test_total_market_fallback_proxies_enabled_when_total_market_sparse(
        self,
        mocked_btc,
        mocked_total,
        mocked_onchain,
        mocked_fear,
        mocked_social,
    ) -> None:
        mocked_btc.return_value = self.btc_price
        sparse_total = pd.Series(np.nan, index=self.index, name="total_market_cap")
        sparse_total.iloc[-20:] = self.total_market.iloc[-20:]
        mocked_total.return_value = sparse_total
        mocked_onchain.return_value = self.onchain
        mocked_fear.return_value = self.fear_greed
        mocked_social.return_value = self.social

        result = run_pipeline(self.cfg)
        metric_health = result.metric_health
        proxy_rows = metric_health[
            (metric_health["category"] == "price_structure")
            & (metric_health["target"] == "total_market")
            & (
                metric_health["metric"].isin(
                    [
                        "btc_trend_extension_50d_350d",
                        "btc_running_roi_1y",
                        "btc_log_reg_deviation",
                    ]
                )
            )
        ]
        self.assertFalse(proxy_rows.empty)


if __name__ == "__main__":
    unittest.main()
