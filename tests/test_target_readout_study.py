import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from research import target_readout_study as study
from research import decision_readout as readout


class TargetStudyTests(unittest.TestCase):
    def test_registration_and_implementation_identity_fail_closed(self):
        spec = study.specification()
        self.assertEqual(spec["horizon_months"], 6)
        self.assertEqual(len(spec["market_forecasters"]), 7)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"freeze.json"
            study.freeze(path)
            study.verify(path)
            with self.assertRaises(FileExistsError):
                study.freeze(path)
            with patch.object(study, "runtime", return_value={}):
                with self.assertRaisesRegex(ValueError, "changed after freeze"):
                    study.verify(path)

    def test_engineering_worlds_are_reproducible_and_disjoint_from_assessment(self):
        spec = study.specification()
        left = study.make_world(1, "persistent_drift", spec, engineering=True)
        right = study.make_world(1, "persistent_drift", spec, engineering=True)
        self.assertTrue(left.equals(right))
        assessment_seed = copy.deepcopy(spec)
        assessment_seed["synthetic"]["root_seed"] = spec["synthetic"]["engineering_seed"]+1
        other = study.make_world(1, "persistent_drift", assessment_seed)
        self.assertFalse(left.price.equals(other.price))

    def test_null_world_prices_ignore_state_but_positive_laws_use_it(self):
        spec = study.specification()
        null = study.make_world(3, "null", spec, engineering=True)
        drift = study.make_world(3, "persistent_drift", spec, engineering=True)
        volatility = study.make_world(3, "persistent_volatility", spec, engineering=True)
        np.testing.assert_array_equal(null.exact, drift.exact)
        self.assertFalse(null.price.equals(drift.price))
        self.assertFalse(null.price.equals(volatility.price))

    def test_untrained_fallback_is_exactly_fixed_dca(self):
        price = np.arange(1, 49, dtype=float)
        missing = study.ledger(price, np.full(48, np.nan), np.zeros(48, bool))
        fixed = study.ledger(price, np.zeros(48), np.ones(48, bool), mode="fixed")
        self.assertTrue(missing.equals(fixed))
        self.assertAlmostEqual(missing.buy.sum(), 48)

    def test_native_policy_has_no_hidden_fixed_dca_fallback(self):
        result = study.ledger(np.ones(48), np.ones(48), np.zeros(48, bool), mode="native")
        self.assertTrue(result.buy.iloc[:-1].eq(0).all())
        self.assertEqual(result.sweep.iloc[-1], 48)

    def test_deadline_and_terminal_deployment_do_not_borrow(self):
        result = study.ledger(np.arange(1, 49), np.ones(48), np.ones(48, bool), mode="native", cap=6)
        self.assertTrue(result.cash.ge(0).all())
        self.assertEqual(result.buy.iloc[6], 1)
        self.assertLessEqual(result.cash.max(), 6)
        self.assertAlmostEqual(result.buy.sum(), 48)

    def test_price_only_forecast_cannot_consume_privileged_scalar(self):
        frame = study.make_world(2, "persistent_volatility", study.specification(), engineering=True)
        before = readout.forecast_at(frame, 70, feature="price_only")
        frame["exact"] = frame.exact*1000
        frame["nuisance"] = 999
        after = readout.forecast_at(frame, 70, feature="price_only")
        self.assertEqual(before, after)

    def test_snapshot_captures_bytes_and_rejects_wrong_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"input.csv"
            path.write_text("a\n1\n")
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                study.capture_frame(path, "bad")

    def test_engineering_end_to_end_common_support_and_serialization(self):
        spec = copy.deepcopy(study.specification())
        spec["synthetic"]["monthly_rows"] = 90
        spec["synthetic"]["horizons"] = [6]
        with tempfile.TemporaryDirectory() as tmp:
            rows = study.evaluate_world(8, "persistent_drift", spec, Path(tmp), engineering=True)
            self.assertEqual(len(rows), 12)
            self.assertEqual({row["scored_n"] for row in rows}, {9})
            for row in rows:
                self.assertTrue(np.isfinite(row["crps"]))

    def test_native_reference_and_capped_policy_match_frozen_existing_results(self):
        frame = study.market_frame(study.specification())
        reference_path = study.ROOT/"docs/artifacts/dca-diagnosis-2026-11-09/windows.csv"
        import pandas as pd
        reference = pd.read_csv(reference_path)
        risk = frame.dca_risk.shift(1).to_numpy()
        for start in range(len(frame)-47):
            window = frame.iloc[start:start+48]
            for arm, cap in (("incumbent", None), ("six_month_deadline", 6)):
                result = study.ledger(window.price, risk[start:start+48], np.ones(48, bool), mode="native", cap=cap)
                row = reference[(reference.start_date == str(window.index[0].date())) & reference.arm.eq(arm)].iloc[0]
                self.assertAlmostEqual(result.units.iloc[-1], row.btc_units, places=13)

    def test_world_comparisons_keep_pairs_and_reject_missing_histories(self):
        spec = copy.deepcopy(study.specification())
        spec["synthetic"]["world_ids"] = [0, 1]
        rows = []
        for world in (0, 1):
            for method in spec["readouts"]:
                for arm, effect in (("price_only", 0.), ("nuisance", .1), ("exact", -.1)):
                    rows.append({"world_id": world, "law": "engineering", "horizon": 6,
                                 "method": method, "arm": arm, "crps": 1+world+effect,
                                 "brier": .2, "coverage80": .8, "width80": 1.})
        summary = study.summarize_worlds(rows, spec)
        exact = next(r for r in summary if r["method"] == "gaussian_expanding" and r["arm"] == "exact")
        self.assertAlmostEqual(exact["gain_vs_own_price_only"], .1)
        np.testing.assert_allclose(exact["gain_ci95_pointwise"], [.1, .1])
        with self.assertRaises(AssertionError):
            study.summarize_worlds(rows[:-1], spec)


if __name__ == "__main__":
    unittest.main()
