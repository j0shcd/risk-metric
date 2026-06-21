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


if __name__ == "__main__":
    unittest.main()
