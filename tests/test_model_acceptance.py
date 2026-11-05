import csv
from contextlib import contextmanager
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from risk_engine.model_acceptance import (
    FROZEN_DATA_PATHS, build_candidate_summary, compare_model_summaries,
    current_identity, model_changed,
)


@contextmanager
def portable_project():
    """Exercise the real CI setup with tracked inputs and no local overrides."""
    project = Path(__file__).resolve().parents[1]
    workflow = (project / ".github/workflows/ci-quality-and-benchmark.yml").read_text()
    steps = re.split(r"(?m)^      - name: ", workflow)[1:]
    prepare = next((step for step in steps if step.startswith("Prepare model acceptance runtime\n")), None)
    assert prepare is not None, "Missing model acceptance runtime setup"
    unit_tests = next(step for step in steps if step.startswith("Run unit tests\n"))
    assert steps.index(prepare) < steps.index(unit_tests), "Runtime must exist before tests and acceptance"
    command = re.search(r"^        run: (.+)$", prepare, re.MULTILINE).group(1)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        shutil.copytree(project / "risk_engine", root / "risk_engine", ignore=shutil.ignore_patterns("__pycache__"))
        (root / "config").mkdir()
        for name in ("model_acceptance.json", "model_acceptance_runtime.json", "model_acceptance_canonical.json"):
            shutil.copy2(project / "config" / name, root / "config" / name)
        for name in FROZEN_DATA_PATHS:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(project / name, target)
        assert not (root / "config/runtime.json").exists()
        subprocess.run(["bash", "-eu", "-c", command], cwd=root, check=True)
        yield root


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

            with portable_project() as project:
                candidate = build_candidate_summary(root, project)
            self.assertEqual(candidate["metrics"]["derisking_calmar_delta_vs_hold"], 0.31)
            self.assertTrue(candidate["metrics"]["dca_causality_gate_passed"])
            self.assertTrue(candidate["metrics"]["signal_horizon_48m_gate_passed"])
            self.assertTrue(candidate["metrics"]["availability_gate_passed"])

    def test_model_change_detection_ignores_data_identity(self) -> None:
        with portable_project() as project:
            candidate = build_identity_summary(project)
            data = project / FROZEN_DATA_PATHS[0]
            data.write_bytes(data.read_bytes() + b"\n")
            self.assertNotEqual(current_identity(project)["data_fingerprint"], candidate["identity"]["data_fingerprint"])
            self.assertFalse(model_changed(candidate, project))

    def test_ci_runtime_produces_identity_in_clean_checkout(self) -> None:
        with portable_project() as project:
            identity = current_identity(project)
            # A future candidate must reach the acceptance gate, so do not bind
            # unit tests to the repository's current canonical fingerprint.
            canonical = {"identity": identity, "metrics": {}}
            self.assertFalse(model_changed(canonical, project))
            runtime = project / "config/runtime.json"
            runtime.write_bytes(runtime.read_bytes() + b"\n")
            self.assertTrue(model_changed(canonical, project))

    def test_ci_runtime_contains_no_credentials(self) -> None:
        project = Path(__file__).resolve().parents[1]
        runtime = json.loads((project / "config/model_acceptance_runtime.json").read_text())
        for key, value in runtime.items():
            if key.endswith("_api_key") or "token" in key or "secret" in key:
                self.assertFalse(value, key)


def build_identity_summary(project: Path) -> dict:
    return {"identity": current_identity(project), "metrics": {}}


if __name__ == "__main__":
    unittest.main()
