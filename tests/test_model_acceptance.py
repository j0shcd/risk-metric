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

    def test_produces_candidate_from_registered_evaluation_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tables").mkdir()
            fields = [
                "hypothesis_id", "auc", "eligible_for_aggregate",
                "passes_shift_leakage_probe", "passes_regime_concentration_gate",
            ]
            with (root / "tables" / "walkforward_by_label.csv").open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                for hypothesis, auc in [
                    ("dca_risk_accumulation_6m", 0.61),
                    ("dca_risk_derisk_6m", 0.62),
                    ("dca_risk_derisk_12m", 0.63),
                ]:
                    writer.writerow({
                        "hypothesis_id": hypothesis,
                        "auc": auc,
                        "eligible_for_aggregate": "True",
                        "passes_shift_leakage_probe": "True",
                        "passes_regime_concentration_gate": "True",
                    })
            with (root / "tables" / "strategy_results.csv").open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=[
                    "strategy", "policy_family", "money_weighted_return", "max_drawdown",
                ])
                writer.writeheader()
                writer.writerow({
                    "strategy": "dynamic_dca", "policy_family": "production_dca_cashflow",
                    "money_weighted_return": 0.2, "max_drawdown": -0.4,
                })
            with (root / "tables" / "availability_calendar.csv").open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["availability_assumption"])
                writer.writeheader()
                writer.writerow({"availability_assumption": "daily close available next day"})

            project = Path(__file__).resolve().parents[1]
            candidate = build_candidate_summary(root, project)
            self.assertEqual(candidate["metrics"]["dca_risk_derisk_12m_auc"], 0.63)
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
