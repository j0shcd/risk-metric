import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from research import forecast_falsification
from research.forecast_falsification import FalsificationConfig, run_falsification


REFERENCE_PATH = Path(__file__).resolve().parents[1] / "docs/artifacts/forecast-pilot-2026-11-06.json"


class ForecastFalsificationTests(unittest.TestCase):
    def test_v1_code_is_the_reference_being_falsified(self):
        reference = json.loads(REFERENCE_PATH.read_text())
        root = REFERENCE_PATH.parents[2]
        for name, digest in reference["code_sha256"].items():
            self.assertEqual(hashlib.sha256((root / "research" / name).read_bytes()).hexdigest(), digest)

    def test_four_experiments_have_distinct_eligibility_and_oracle_claims(self):
        reference = json.loads(REFERENCE_PATH.read_text())
        with patch.object(forecast_falsification, "run_campaign", wraps=forecast_falsification.run_campaign) as scorer:
            summary, campaigns, attempts, predictions = run_falsification(FalsificationConfig(worlds=2), reference)
        self.assertEqual(scorer.call_count, 10)  # Five eligible families, no revised or short-path scoring.
        self.assertEqual(summary["frozen_iid_threshold"], reference["null_audit_threshold"])
        self.assertEqual(summary["families"]["revised"]["status_counts"], {"ineligible": 2})
        self.assertEqual(summary["families"]["overlap_short_min24"]["status_counts"], {"insufficient_evidence": 1})
        self.assertFalse(summary["real_market_models_evaluated"])
        self.assertEqual(summary["families"]["redundant"]["metrics"]["context_plus_indicator_oracle_loss_delta"]["median"], 0)
        self.assertEqual(len(attempts), 2 * (reference["config"]["candidates"] + 4))
        self.assertEqual(len(predictions), 10 * reference["config"]["phase_rows"])
        self.assertEqual(len(campaigns), 13)
        for row in predictions:
            self.assertLessEqual(row["publication_step"], row["decision_step"])
            self.assertLess(row["decision_step"], row["execution_step"])
            self.assertLess(row["execution_step"], row["outcome_end_step"])
            self.assertLessEqual(row["outcome_end_step"], row["label_available_step"])

    def test_invalid_reference_or_configuration_is_not_silently_recalibrated(self):
        reference = json.loads(REFERENCE_PATH.read_text())
        with self.assertRaises(ValueError):
            run_falsification(FalsificationConfig(worlds=0), reference)
        with self.assertRaises(ValueError):
            run_falsification(FalsificationConfig(worlds=1), {**reference, "protocol": "different"})
        with self.assertRaises(ValueError):
            run_falsification(FalsificationConfig(worlds=1), {**reference, "null_audit_threshold": float("nan")})


if __name__ == "__main__":
    unittest.main()
