import unittest

import numpy as np
import pandas as pd

from risk_engine.scoring import score_target
from risk_engine.types import FeatureBundle


def _bundle(
    index: pd.DatetimeIndex,
    name: str,
    category: str,
    target: str,
    signed_signal: float,
    attention: float,
    reliability: float = 1.0,
) -> FeatureBundle:
    frame = pd.DataFrame(
        {
            "signed_signal": signed_signal,
            "attention": attention,
            "reliability": reliability,
        },
        index=index,
    )
    return FeatureBundle(name=name, category=category, target=target, frame=frame)


class ScoringBehaviorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.index = pd.date_range("2024-01-01", periods=50, freq="D")
        self.weights = {"price_structure": 1.0}

    def test_crowding_lifts_consensus_signal_and_boosts_attention(self) -> None:
        consensus_bundles = [
            _bundle(self.index, "m1", "price_structure", "btc", signed_signal=0.4, attention=0.5),
            _bundle(self.index, "m2", "price_structure", "btc", signed_signal=0.4, attention=0.5),
            _bundle(self.index, "m3", "price_structure", "btc", signed_signal=0.4, attention=0.5),
        ]
        mixed_bundles = [
            _bundle(self.index, "m1", "price_structure", "btc", signed_signal=0.9, attention=0.5),
            _bundle(self.index, "m2", "price_structure", "btc", signed_signal=0.9, attention=0.5),
            _bundle(self.index, "m3", "price_structure", "btc", signed_signal=-0.6, attention=0.5),
        ]

        consensus = score_target(self.index, consensus_bundles, self.weights, target="btc")
        mixed = score_target(self.index, mixed_bundles, self.weights, target="btc")

        self.assertGreater(float(consensus.signal.mean()), float(mixed.signal.mean()))

        consensus_breakdown = consensus.category_breakdown
        mixed_breakdown = mixed.category_breakdown
        self.assertIn("category_price_structure_crowding_consensus", consensus_breakdown.columns)
        self.assertIn("category_price_structure_disagreement", consensus_breakdown.columns)
        self.assertGreater(
            float(consensus_breakdown["category_price_structure_crowding_consensus"].mean()),
            float(mixed_breakdown["category_price_structure_crowding_consensus"].mean()),
        )
        self.assertGreater(
            float(consensus_breakdown["category_price_structure_crowding_attention_boost"].mean()),
            float(mixed_breakdown["category_price_structure_crowding_attention_boost"].mean()),
        )

    def test_reliability_adjusts_effective_weight(self) -> None:
        strong = _bundle(self.index, "strong", "price_structure", "btc", signed_signal=0.8, attention=0.7, reliability=1.0)
        weak = _bundle(self.index, "weak", "price_structure", "btc", signed_signal=0.8, attention=0.7, reliability=0.1)

        score_strong = score_target(self.index, [strong], self.weights, target="btc")
        score_weak = score_target(self.index, [weak], self.weights, target="btc")

        eff_strong = score_strong.category_breakdown["category_price_structure_effective_weight"].mean()
        eff_weak = score_weak.category_breakdown["category_price_structure_effective_weight"].mean()
        self.assertGreater(float(eff_strong), float(eff_weak))

    def test_ineligible_metrics_equal_removing_them_on_each_date(self):
        primary = _bundle(self.index, "primary", "price_structure", "btc", .3, .4, .9)
        missing = _bundle(self.index, "missing", "price_structure", "btc", np.nan, np.nan)
        proxy = _bundle(self.index, "proxy", "price_structure", "btc", -.8, .7, .35)
        proxy.frame["eligible"] = np.arange(len(self.index)) % 2 == 0
        routed = score_target(self.index, [primary, missing, proxy], self.weights, "btc")
        active = score_target(self.index, [primary, missing, _bundle(
            self.index, "proxy", "price_structure", "btc", -.8, .7, .35)], self.weights, "btc")
        inactive = score_target(self.index, [primary, missing], self.weights, "btc")
        for enabled, expected in ((True, active), (False, inactive)):
            dates = self.index[proxy.frame["eligible"].eq(enabled)]
            for field in ("signal", "attention", "confidence", "coverage", "category_breakdown"):
                actual_values, expected_values = getattr(routed, field).loc[dates], getattr(expected, field).loc[dates]
                if isinstance(actual_values, pd.Series):
                    pd.testing.assert_series_equal(actual_values, expected_values, check_exact=True)
                else:
                    pd.testing.assert_frame_equal(actual_values, expected_values, check_exact=True)
            pd.testing.assert_frame_equal(routed.metric_breakdown.loc[dates, expected.metric_breakdown.columns],
                                          expected.metric_breakdown.loc[dates], check_exact=True)
        inactive_dates = self.index[~proxy.frame["eligible"]]
        self.assertTrue(routed.metric_breakdown.loc[inactive_dates, "metric_proxy_effective_weight"].eq(0).all())
        self.assertTrue(routed.metric_breakdown.loc[inactive_dates, "metric_proxy_signal"].isna().all())

    def test_wholly_ineligible_category_has_no_coverage_weight(self):
        primary = _bundle(self.index, "primary", "price_structure", "btc", .3, .4, .9)
        inactive = _bundle(self.index, "inactive", "social", "btc", -.8, .7, .35)
        inactive.frame["eligible"] = False
        weights = {"price_structure": .5, "social": .5}
        expected = score_target(self.index, [primary], weights, "btc")
        actual = score_target(self.index, [primary, inactive], weights, "btc")
        for field in ("signal", "attention", "confidence", "coverage"):
            pd.testing.assert_series_equal(getattr(actual, field), getattr(expected, field), check_exact=True)
        self.assertTrue(actual.category_breakdown["category_social_effective_weight"].eq(0).all())
        absent = score_target(self.index, [inactive], weights, "btc")
        for field in ("signal", "attention", "confidence", "coverage"):
            self.assertTrue(getattr(absent, field).isna().all())


if __name__ == "__main__":
    unittest.main()
