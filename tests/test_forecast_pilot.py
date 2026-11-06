from dataclasses import replace
from contextlib import redirect_stderr
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from research.forecast_pilot import (
    PilotConfig, data_feasibility, main, run_campaign, run_pilot,
    skill, synthetic_phases, validate_phases, write_report,
)


SMALL = PilotConfig(candidates=4, calibration_worlds=20, evaluation_worlds=10, fit_rows=96, phase_rows=48)


class ForecastPilotTests(unittest.TestCase):
    def test_audit_outcomes_cannot_choose_the_winner(self):
        phases = synthetic_phases(SMALL, 2, 4, .5)
        first, attempts, _ = run_campaign(phases, SMALL)
        changed_audit = replace(phases[-1], outcomes=phases[-1].outcomes * -100)
        changed, changed_attempts, _ = run_campaign((*phases[:-1], changed_audit), SMALL)
        self.assertEqual(first["selected_candidate"], changed["selected_candidate"])
        self.assertEqual(attempts, changed_attempts)
        self.assertNotEqual(first["audit_skill"], changed["audit_skill"])

    def test_unresolved_training_or_selection_outcomes_invalidate_run(self):
        phases = synthetic_phases(SMALL, 1, 0, 0)
        for index in range(3):
            with self.subTest(index=index):
                changed = list(phases)
                changed[index] = replace(phases[index], label_available_step=np.full(len(phases[index].outcomes), phases[index + 1].decision_step[0] + 1))
                with self.assertRaisesRegex(ValueError, "unresolved"):
                    validate_phases(tuple(changed), SMALL.candidates)

    def test_missing_candidate_rows_cannot_select_a_convenient_sample(self):
        phases = list(synthetic_phases(SMALL, 1, 0, 0))
        invalid = phases[2].indicators.copy()
        invalid[0, 0] = np.nan
        phases[2] = replace(phases[2], indicators=invalid)
        with self.assertRaisesRegex(ValueError, "common sample"):
            run_campaign(tuple(phases), SMALL)
        with self.assertRaises(ValueError):
            skill(np.array([1]), np.array([1, 2]))

    def test_known_information_and_wrong_direction_are_distinguished(self):
        # Same generated features/innovations across strengths isolate information.
        strong, _, _ = run_campaign(synthetic_phases(SMALL, 20, 3, 2), SMALL)
        inverted, _, _ = run_campaign(synthetic_phases(SMALL, 20, 3, 2, inverted=True), SMALL)
        self.assertGreater(strong["audit_skill"], 10)
        self.assertLess(inverted["audit_skill"], 1)

    def test_complete_search_registry_and_independent_threshold_worlds(self):
        summary, worlds, attempts, predictions = run_pilot(SMALL)
        expected_worlds = SMALL.calibration_worlds + 4 * SMALL.evaluation_worlds
        self.assertEqual(len(worlds), expected_worlds)
        self.assertEqual(len(attempts), expected_worlds * SMALL.candidates)
        self.assertEqual(len(predictions), expected_worlds * SMALL.phase_rows)
        threshold_values = sorted(row["audit_skill"] for row in worlds if row["family"] == "threshold_null")
        self.assertEqual(summary["null_audit_threshold"], max(0, threshold_values[-1]))
        # Reports are deterministic and do not claim financial significance.
        self.assertEqual(summary, run_pilot(SMALL)[0])
        self.assertFalse(summary["real_market_models_evaluated"])
        self.assertEqual(summary["status"], "synthetic_diagnostic_only")

    def test_later_outcomes_cannot_change_a_fixed_candidates_forecasts(self):
        config = replace(SMALL, candidates=1)
        phases = synthetic_phases(config, 8, 2, 1)
        _, _, before = run_campaign(phases, config)
        changed = (*phases[:2], replace(phases[2], outcomes=-100 * phases[2].outcomes), replace(phases[3], outcomes=100 * phases[3].outcomes))
        _, _, after = run_campaign(changed, config)
        for left, right in zip(before, after):
            for key in ("q10", "q50", "q90"):
                self.assertEqual(left[key], right[key])

    def test_threshold_uses_nonextreme_null_order_and_strict_exceedance(self):
        config = replace(SMALL, candidates=1, calibration_worlds=200, evaluation_worlds=1)
        # ceil(201*.95)=191: sorted zero-based value190. Audit values must not
        # influence that threshold; equality is not a declaration.
        values = iter([*range(200), 190, 191, 1e9, -1e9])
        def fake_campaign(*_):
            return {"audit_skill": next(values), "development_skill": 1}, [], []
        with patch("research.forecast_pilot.run_campaign", side_effect=fake_campaign):
            summary, *_ = run_pilot(config)
        self.assertEqual(summary["null_audit_threshold"], 190)
        self.assertEqual(summary["threshold_order_1based"], 191)
        self.assertEqual(summary["families"]["evaluation_null"]["declarations"], 0)
        self.assertEqual(summary["families"]["weak_signal"]["declarations"], 1)

    def test_feasibility_rejects_partial_month_and_uses_execution_maturity(self):
        dates = pd.date_range("2020-01-01", "2021-07-30", freq="D")
        frame = pd.DataFrame({"btc_price": 100., "dca_risk": .5}, index=dates)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.csv"
            frame.to_csv(path)
            result = data_feasibility(path, [3], minimum_labels=2)
            self.assertEqual(result["last_complete_month"], "2021-06-30")
            # Jan decision -> Feb execution -> May outcome -> Jun 1 availability.
            # Feb decision resolves Jun 30 -> Jul 1, so second label is usable Jul 31.
            self.assertEqual(result["horizons"][0]["first_cutoff_with_minimum_raw_labels"], "2020-07-31")
            self.assertEqual(result["horizons"][0]["complete_common_entry_rows"], 14)
            self.assertEqual(len(result["monthly_coverage"]), 18)
            self.assertTrue(all(row["price_usable"] for row in result["monthly_coverage"]))
            before = result["horizons"][0]["complete_common_entry_rows"]
            frame.loc["2020-05-31", "btc_price"] = np.nan
            frame.to_csv(path)
            after = data_feasibility(path, [3], minimum_labels=2)["horizons"][0]["complete_common_entry_rows"]
            self.assertLess(after, before)  # No last-finite-value carry across the gap.

    def test_report_is_exclusive_and_manifest_binds_every_output(self):
        summary, worlds, attempts, predictions = run_pilot(SMALL)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "run with spaces $(literal)"
            write_report(target, summary, worlds, attempts, predictions)
            original = (target / "summary.json").read_bytes()
            with self.assertRaises(FileExistsError):
                write_report(target, summary, worlds, attempts, predictions)
            self.assertEqual(original, (target / "summary.json").read_bytes())
            manifest = json.loads((target / "manifest.json").read_text())
            for name, expected in manifest["files"].items():
                self.assertEqual(hashlib.sha256((target / name).read_bytes()).hexdigest(), expected)
            self.assertTrue((target / "COMPLETE").exists())
            link = Path(directory).resolve() / "link"
            link.symlink_to(target, target_is_directory=True)
            with self.assertRaises(ValueError):
                write_report(link / "escape", summary, worlds, attempts, predictions)
            self.assertFalse((target / "escape").exists())

    def test_interrupted_report_has_no_completion_marker_and_cannot_overwrite(self):
        summary, worlds, attempts, predictions = run_pilot(SMALL)
        from research import forecast_pilot
        publish = forecast_pilot._publish_exclusive
        def interrupted(path, payload):
            if path.name == "attempts.csv":
                raise OSError("simulated interruption")
            publish(path, payload)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "partial"
            with patch.object(forecast_pilot, "_publish_exclusive", side_effect=interrupted):
                with self.assertRaises(OSError):
                    write_report(target, summary, worlds, attempts, predictions)
            self.assertTrue((target / "manifest.json").exists())
            self.assertFalse((target / "COMPLETE").exists())
            with self.assertRaises(FileExistsError):
                write_report(target, summary, worlds, attempts, predictions)

    def test_cli_requires_explicit_horizons_for_real_data(self):
        with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):
            main(["--output-dir", "unused", "--artifact-series", "unused.csv"])
        with self.assertRaises(ValueError):
            run_pilot(replace(SMALL, calibration_worlds=2))


if __name__ == "__main__":
    unittest.main()
