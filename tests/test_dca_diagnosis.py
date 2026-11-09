import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd


spec = importlib.util.spec_from_file_location(
    "dca_diagnosis", Path(__file__).resolve().parents[1] / "scripts/diagnose-dca-underperformance.py"
)
diagnosis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnosis)


class DcaDiagnosisTests(unittest.TestCase):
    def test_parse_captured_bytes_despite_path_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.csv"
            raw = b"value\n1\n"
            path.write_bytes(raw)
            parse = pd.read_csv

            def replace_then_parse(source, **kwargs):
                path.write_bytes(b"value\n999\n")
                return parse(source, **kwargs)

            with patch.object(pd, "read_csv", side_effect=replace_then_parse):
                result = diagnosis.captured_csv(path, hashlib.sha256(raw).hexdigest())
            self.assertEqual(result.value.iloc[0], 1)

    def test_wrong_input_identity_fails_before_parse(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.csv"
            path.write_bytes(b"value\n1\n")
            with patch.object(pd, "read_csv") as parse:
                with self.assertRaises(ValueError):
                    diagnosis.captured_csv(path, "wrong")
                parse.assert_not_called()

    def test_flat_price_same_units_for_every_purchase_timing(self):
        price = np.full(48, 100.0)
        for scores in (np.zeros(48), np.ones(48), np.full(48, np.nan)):
            ledger, cohorts = diagnosis.simulate(price, scores)
            self.assertAlmostEqual(ledger.units.iloc[-1], 48 * .998 / 100)
            self.assertAlmostEqual(cohorts.units_delta.sum(), 0)
            self.assertAlmostEqual(ledger.buy.sum(), 48)

    def test_delay_cost_changes_sign_with_price_path(self):
        for rising in (True, False):
            price = np.arange(1, 49, dtype=float)
            if not rising:
                price = price[::-1]
            fixed, _ = diagnosis.simulate(price, np.zeros(48), kind="fixed")
            delayed, _ = diagnosis.simulate(price, np.ones(48))
            self.assertEqual(delayed.units.iloc[-1] < fixed.units.iloc[-1], rising)

    def test_deadline_clears_old_cohorts_and_bounds_wait(self):
        ledger, cohorts = diagnosis.simulate(np.arange(1, 13), np.ones(12), deadline=6)
        self.assertTrue(ledger.buy.iloc[:6].eq(0).all())
        self.assertEqual(ledger.buy.iloc[6], 1)
        self.assertLessEqual(cohorts.weighted_wait_months.max(), 6)
        self.assertEqual(ledger.cash.iloc[-1], 0)

    def test_future_inputs_do_not_change_prefix_ledger(self):
        price = np.arange(1, 17, dtype=float)
        score = np.linspace(0, 1, 16)
        before, _ = diagnosis.simulate(price, score, deadline=6)
        price[9:] *= 100
        score[9:] = 0
        after, _ = diagnosis.simulate(price, score, deadline=6)
        pd.testing.assert_frame_equal(before.iloc[:9], after.iloc[:9])

    def test_overlay_is_only_a_linear_capital_allocation(self):
        price = np.array([100, 110, 75, 80, 120, 130], dtype=float)
        incumbent, _ = diagnosis.simulate(price, np.ones(6))
        fixed, _ = diagnosis.simulate(price, np.ones(6), kind="fixed")
        overlay, _ = diagnosis.simulate(price, np.ones(6), schedule=diagnosis.overlay_schedule(incumbent))
        self.assertAlmostEqual(overlay.units.iloc[-1], .8 * fixed.units.iloc[-1] + .2 * incumbent.units.iloc[-1])

    def test_overlay_retains_forced_terminal_purchase_attribution(self):
        price = np.arange(1, 13, dtype=float)
        incumbent, _ = diagnosis.simulate(price, np.ones(12))
        overlay, _ = diagnosis.simulate(price, np.ones(12), schedule=diagnosis.overlay_schedule(incumbent))
        self.assertAlmostEqual(overlay.terminal_sweep.sum(), .2 * incumbent.terminal_sweep.sum())

    def test_arm_scores_are_previous_month_values(self):
        index = pd.date_range("2020-01-31", periods=4, freq="ME")
        frame = pd.DataFrame(index=index)
        for column in ["dca_risk", *diagnosis.COMPONENTS.values(), "top_reversal_risk",
                       "bottom_reversal_risk", "cycle_extension_score", "cycle_frenzy_score"]:
            frame[column] = [.1, .9, .2, .8]
        frame["price_only_applied"] = [np.nan, .3, .4, .5]
        arms = diagnosis.score_arms(frame)
        for arm in ["incumbent", "single_top_reversal", "without_cycle_regime", "causal_rank_24"]:
            self.assertTrue(np.isnan(arms[arm].iloc[0]))
            self.assertAlmostEqual(arms[arm].iloc[1], .1)
        self.assertEqual(arms["price_only"].iloc[1], .3)


if __name__ == "__main__":
    unittest.main()
