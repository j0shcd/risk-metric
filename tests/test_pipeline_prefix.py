"""Fixed-input history contract at run_pipeline, not just routing helpers.

Sources: appended daily prices, total-market availability/values, on-chain,
sentiment and cycle context. Source modes/config stay fixed. Sinks: every
series column plus category/metric attribution. Aggregate reports, current
health/as-of metadata and newly resolved outcome diagnostics are excluded.
Only reporting functions and source loaders are stubbed; feature building,
normalization, scoring, cycle decisions, calibration and DCA remain real.
"""
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd

from risk_engine.config import RuntimeConfig
from risk_engine import pipeline
from risk_engine.pipeline import run_pipeline


# Independently maintained sink inventory: new output columns require a conscious
# contract decision; none are silently excluded by a prefix/name heuristic.
SERIES_COLUMNS = set("""
btc_risk_signal btc_risk_attention btc_risk_confidence btc_risk_coverage
total_market_risk_signal total_market_risk_attention total_market_risk_confidence total_market_risk_coverage
headline_attention trend_composite_score cycle_extension_score confidence_score
headline_btc_mix_weight headline_total_market_mix_weight btc_price total_market_cap
mvrv_implied_profitability_proxy cycle_frenzy_score cycle_accumulation_score
cycle_p_frenzy cycle_p_accumulation cycle_confidence cycle_position cycle_signal_regime
cycle_signal_cooldown_state price_extremity_pct momentum_exhaustion_pct attention_blowoff_pct
top_reversal_risk bottom_reversal_risk attention_score dca_top_reversal_component
dca_bottom_reversal_component dca_cycle_extension_component dca_cycle_regime_component
dca_component_coverage dca_risk top_alert_operational bottom_alert_operational
top_alert_threshold_operational bottom_alert_threshold_operational
top_alert_cooldown_state_operational bottom_alert_cooldown_state_operational
""".split())


class PipelinePrefixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = pd.date_range('2018-01-01', '2020-07-31', freq='D')
        t = np.arange(len(cls.index))
        cls.price = pd.Series(100 * np.exp(t / 1500 + .3 * np.sin(t / 63)), index=cls.index)
        cls.total = pd.Series(1e9 * np.exp(t / 2400 + .4 * np.cos(t / 81)), index=cls.index)
        # 364 observations on Dec 31, then the 365-observation boundary.
        cls.total.loc[:'2019-01-01'] = np.nan
        # 19 missing points in a 90-point tail cross the strict .8 boundary.
        cls.total.loc['2020-04-12':'2020-04-30'] = np.nan
        cls.onchain = pd.DataFrame({'mvrv_ratio_z_proxy': np.sin(t / 90),
                                    'puell_multiple': 1 + .3 * np.cos(t / 80)}, index=cls.index)
        cls.fear = pd.Series(50 + 30 * np.sin(t / 45), index=cls.index)
        cls.social = pd.DataFrame({'google_trends_interest': 50 + 10 * np.cos(t / 51)}, index=cls.index)
        cls.context = pd.DataFrame({'btc_price': cls.price, 'btc_volume_usd': 1e8 + t * 1e5,
                                    'dxy': 100 + np.sin(t / 37)}, index=cls.index)

    def produce(self, end, profile='free_stable', perturb_after=None):
        root = Path('/synthetic-pipeline-prefix-no-io')
        cfg = RuntimeConfig(project_root=root, data_dir=root, output_dir=root, cache_dir=root,
                            data_profile=profile)
        inputs = {'btc_price': self.price, 'total_market_cap': self.total,
                  'onchain_metrics': self.onchain, 'fear_greed_index': self.fear,
                  'social_metrics': self.social, 'cycle_market_context': self.context}
        empty = pd.DataFrame()
        report = SimpleNamespace(summary=empty, by_label=empty, by_signal=empty,
                                 window_stats=empty, config={}, warnings=[])
        self.assertEqual({name for name in vars(pipeline) if name.startswith('load_')},
                         {'load_' + name for name in inputs} | {'load_runtime_config'})
        with ExitStack() as stack:
            stack.enter_context(patch('requests.sessions.Session.request', side_effect=AssertionError('network forbidden')))
            for name, values in inputs.items():
                captured = values.loc[:end].copy()
                if perturb_after is not None:
                    future = captured.index > pd.Timestamp(perturb_after)
                    captured.loc[future] = captured.loc[future] * 3.7 + 11
                stack.enter_context(patch('risk_engine.pipeline.load_' + name, return_value=captured))
            stack.enter_context(patch('risk_engine.pipeline._load_benchmark_baseline', return_value={}))
            stack.enter_context(patch('risk_engine.pipeline.evaluate_benchmark', return_value=report))
            for owner in ('pipeline', 'cycle_model'):
                stack.enter_context(patch('risk_engine.' + owner + '._build_financial_benchmark_outputs',
                                          return_value=(empty, empty)))
                stack.enter_context(patch('risk_engine.' + owner + '._build_backtest_report', return_value=empty))
            return run_pipeline(cfg)

    def assert_prefix(self, prefix, full):
        self.assertEqual(set(prefix.series), SERIES_COLUMNS)
        self.assertEqual(set(full.series), SERIES_COLUMNS)
        pd.testing.assert_frame_equal(prefix.series, full.series.loc[prefix.series.index], check_exact=True)
        for attribute in ('category_breakdowns', 'metric_breakdowns', 'feature_frames'):
            earlier, later = getattr(prefix, attribute), getattr(full, attribute)
            self.assertEqual(set(earlier), set(later))
            for name, frame in earlier.items():
                pd.testing.assert_frame_equal(frame, later[name].loc[frame.index], check_exact=True)

    def test_future_coverage_cannot_rewrite_dated_outputs(self):
        full = self.produce('2020-07-31')
        # Includes both sides of 364/365 observations and 72/90 versus 71/90
        # tail coverage, as well as restoration after the outage leaves the tail.
        for end in ('2019-12-31', '2020-01-01', '2020-04-29', '2020-04-30'):
            with self.subTest(end=end):
                self.assert_prefix(self.produce(end), full)
        proxy = full.feature_frames['btc_running_roi_1y__total_market__price_structure']
        self.assertEqual(proxy.loc[['2019-12-31', '2020-01-01', '2020-04-29',
                                    '2020-04-30', '2020-07-31'], 'eligible'].tolist(),
                         [True, False, False, True, False])
        self.assertTrue(full.series['dca_risk'].notna().any())
        self.assertTrue(full.series['total_market_risk_signal'].notna().any())

    def test_future_values_cannot_rewrite_extended_profile(self):
        prefix = self.produce('2019-12-31', profile='extended')
        future = self.produce('2020-07-31', profile='extended', perturb_after='2019-12-31')
        self.assert_prefix(prefix, future)


if __name__ == '__main__':
    unittest.main()
