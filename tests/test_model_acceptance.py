import csv
import json
import tempfile
import unittest
from pathlib import Path

from risk_engine.model_acceptance import build_candidate_summary, compare_model_summaries, model_changed


POLICY = {
    "primary": {"metric": "primary", "min_improvement": 0.01},
    "guardrails": [{"metric": "guardrail", "min_delta": -0.02}],
    "required_true": ["leakage_passed"],
}


def summary(model: str, *, primary: float, guardrail: float, data: str = "data-a") -> dict:
    return {
        "identity": {
            "release_id": f"release-{model}",
            "model_fingerprint": model,
            "config_hash": f"config-{model}",
            "data_fingerprint": data,
        },
        "metrics": {
            "primary": primary,
            "guardrail": guardrail,
            "leakage_passed": True,
        },
    }


class ModelAcceptanceTests(unittest.TestCase):
    def test_accepts_meaningful_improvement_with_noninferior_guardrail(self) -> None:
        report = compare_model_summaries(
            summary("candidate", primary=0.62, guardrail=0.59),
            summary("canonical", primary=0.60, guardrail=0.60),
            POLICY,
        )
        self.assertTrue(report.passed)
        self.assertEqual(report.failures, [])
        self.assertEqual(report.candidate_identity["model_fingerprint"], "candidate")

    def test_rejects_trivial_primary_change(self) -> None:
        report = compare_model_summaries(
            summary("candidate", primary=0.605, guardrail=0.60),
            summary("canonical", primary=0.60, guardrail=0.60),
            POLICY,
        )
        self.assertFalse(report.passed)
        self.assertIn("primary_improvement_failed:primary", report.failures)

    def test_rejects_different_data_or_guardrail_regression(self) -> None:
        report = compare_model_summaries(
            summary("candidate", primary=0.62, guardrail=0.55, data="data-b"),
            summary("canonical", primary=0.60, guardrail=0.60),
            POLICY,
        )
        self.assertFalse(report.passed)
        self.assertIn("data_fingerprint_mismatch", report.failures)
        self.assertIn("non_inferiority_failed:guardrail", report.failures)

    def test_produces_candidate_from_dca_evidence_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tables").mkdir()
            fields = [
                "test",
                "median_terminal_wealth_delta_pct_vs_fixed",
                "median_cashflow_delta_fixed_buys_risk_sells",
                "median_calmar_delta_vs_hold",
                "median_low_minus_high_forward_return",
            ]
            with (root / "tables" / "dca_evidence_summary.csv").open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow({
                    "test": "accumulation_only",
                    "median_terminal_wealth_delta_pct_vs_fixed": -0.12,
                })
                writer.writerow({
                    "test": "derisking",
                    "median_cashflow_delta_fixed_buys_risk_sells": -0.04,
                    "median_calmar_delta_vs_hold": 0.31,
                })
                writer.writerow({
                    "test": "signal_value",
                    "median_low_minus_high_forward_return": 0.8,
                })
            with (root / "tables" / "dca_causality_audit.csv").open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["passes_causality_audit"])
                writer.writeheader()
                writer.writerow({"passes_causality_audit": "True"})
            with (root / "tables" / "dca_signal_value.csv").open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["horizon_months"])
                writer.writeheader()
                writer.writerow({"horizon_months": 48})
            with (root / "tables" / "availability_calendar.csv").open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["availability_assumption"])
                writer.writeheader()
                writer.writerow({"availability_assumption": "daily close available next day"})

            project = Path(__file__).resolve().parents[1]
            candidate = build_candidate_summary(root, project)
            self.assertEqual(candidate["metrics"]["derisking_calmar_delta_vs_hold"], 0.31)
            self.assertTrue(candidate["metrics"]["dca_causality_gate_passed"])
            self.assertTrue(candidate["metrics"]["signal_horizon_48m_gate_passed"])
            self.assertTrue(candidate["metrics"]["availability_gate_passed"])

    def test_model_change_detection_ignores_data_identity(self) -> None:
        project = Path(__file__).resolve().parents[1]
        candidate = build_identity_summary(project)
        candidate["identity"]["data_fingerprint"] = "new-data"
        self.assertFalse(model_changed(candidate, project))


def build_identity_summary(project: Path) -> dict:
    from risk_engine.model_acceptance import current_identity

    return {"identity": current_identity(project), "metrics": {}}


if __name__ == "__main__":
    unittest.main()
