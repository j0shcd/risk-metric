import unittest

import numpy as np
import pandas as pd

from risk_engine.pipeline import add_dca_risk_columns


class DcaRiskTests(unittest.TestCase):
    def test_missing_component_values_remain_missing_and_reduce_coverage(self) -> None:
        index = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"])
        frame = pd.DataFrame(
            {
                "top_reversal_risk": [0.4, np.nan, 0.8],
                "bottom_reversal_risk": [0.6, 0.7, np.nan],
                "cycle_extension_score": [0.2, 0.4, 0.6],
                "cycle_frenzy_score": [0.3, 0.4, 0.5],
            },
            index=index,
        )

        output = add_dca_risk_columns(frame)

        self.assertTrue(np.isnan(output.loc[index[1], "dca_top_reversal_component"]))
        self.assertTrue(np.isnan(output.loc[index[2], "dca_bottom_reversal_component"]))
        self.assertEqual(output.loc[index[0], "dca_component_coverage"], 1.0)
        self.assertEqual(output.loc[index[1], "dca_component_coverage"], 0.75)
        self.assertEqual(output.loc[index[2], "dca_component_coverage"], 0.75)
        self.assertFalse(output["dca_risk"].dropna().empty)

    def test_bottom_reversal_component_is_inverted_for_dca_risk(self) -> None:
        index = pd.to_datetime(["2026-01-01", "2026-01-02"])
        frame = pd.DataFrame(
            {
                "top_reversal_risk": [0.5, 0.5],
                "bottom_reversal_risk": [0.2, 0.8],
                "cycle_extension_score": [0.5, 0.5],
                "cycle_frenzy_score": [0.5, 0.5],
            },
            index=index,
        )

        output = add_dca_risk_columns(frame)

        self.assertEqual(output.loc[index[0], "dca_bottom_reversal_component"], 0.5)
        self.assertEqual(output.loc[index[1], "dca_bottom_reversal_component"], 0.0)

    def test_dca_risk_fails_closed_below_minimum_component_coverage(self) -> None:
        index = pd.to_datetime(["2026-01-01", "2026-01-02"])
        frame = pd.DataFrame(
            {
                "top_reversal_risk": [0.4, np.nan],
                "bottom_reversal_risk": [0.6, np.nan],
                "cycle_extension_score": [0.2, 0.4],
                "cycle_frenzy_score": [0.3, 0.4],
            },
            index=index,
        )

        output = add_dca_risk_columns(frame)

        self.assertEqual(output.loc[index[1], "dca_component_coverage"], 0.5)
        self.assertTrue(np.isnan(output.loc[index[1], "dca_risk"]))

    def test_future_component_values_cannot_change_past_dca_risk(self) -> None:
        index = pd.date_range("2025-01-01", periods=20, freq="D")
        x = np.arange(len(index), dtype=float)
        frame = pd.DataFrame(
            {
                "top_reversal_risk": 0.1 + 0.02 * x,
                "bottom_reversal_risk": 0.9 - 0.02 * x,
                "cycle_extension_score": 0.2 + 0.03 * x,
                "cycle_frenzy_score": 0.8 - 0.03 * x,
            },
            index=index,
        )
        cutoff = index[11]
        prefix_only = add_dca_risk_columns(frame.loc[:cutoff])

        mutated = frame.copy()
        mutated.loc[mutated.index > cutoff, :] = np.array([1.0, 0.0, 1.0, 0.0])
        full_with_mutated_future = add_dca_risk_columns(mutated)

        columns = [
            "dca_risk",
            "dca_top_reversal_component",
            "dca_bottom_reversal_component",
            "dca_cycle_extension_component",
            "dca_cycle_regime_component",
        ]
        pd.testing.assert_frame_equal(
            prefix_only[columns],
            full_with_mutated_future.loc[:cutoff, columns],
        )


if __name__ == "__main__":
    unittest.main()
