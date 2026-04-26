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
    signed_heat: float,
    attention: float,
    reliability: float = 1.0,
) -> FeatureBundle:
    frame = pd.DataFrame(
        {
            "signed_heat": signed_heat,
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

    def test_crowding_damps_heat_and_boosts_attention(self) -> None:
        consensus_bundles = [
            _bundle(self.index, "m1", "price_structure", "btc", signed_heat=0.4, attention=0.5),
            _bundle(self.index, "m2", "price_structure", "btc", signed_heat=0.4, attention=0.5),
            _bundle(self.index, "m3", "price_structure", "btc", signed_heat=0.4, attention=0.5),
        ]
        mixed_bundles = [
            _bundle(self.index, "m1", "price_structure", "btc", signed_heat=0.9, attention=0.5),
            _bundle(self.index, "m2", "price_structure", "btc", signed_heat=0.9, attention=0.5),
            _bundle(self.index, "m3", "price_structure", "btc", signed_heat=-0.6, attention=0.5),
        ]

        consensus = score_target(self.index, consensus_bundles, self.weights, target="btc")
        mixed = score_target(self.index, mixed_bundles, self.weights, target="btc")

        self.assertLess(float(consensus.heat.mean()), float(mixed.heat.mean()))

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
        strong = _bundle(self.index, "strong", "price_structure", "btc", signed_heat=0.8, attention=0.7, reliability=1.0)
        weak = _bundle(self.index, "weak", "price_structure", "btc", signed_heat=0.8, attention=0.7, reliability=0.1)

        score_strong = score_target(self.index, [strong], self.weights, target="btc")
        score_weak = score_target(self.index, [weak], self.weights, target="btc")

        eff_strong = score_strong.category_breakdown["category_price_structure_effective_weight"].mean()
        eff_weak = score_weak.category_breakdown["category_price_structure_effective_weight"].mean()
        self.assertGreater(float(eff_strong), float(eff_weak))


if __name__ == "__main__":
    unittest.main()
