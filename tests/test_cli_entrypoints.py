import runpy
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from risk_engine.types import RiskOutput
from risk_engine.validation import ValidationResult


class CliEntrypointTests(unittest.TestCase):
    def _result(self) -> RiskOutput:
        idx = pd.date_range("2026-01-01", periods=2, freq="D")
        series = pd.DataFrame({"btc_risk_signal": [0.1, 0.2]}, index=idx)
        return RiskOutput(
            series=series,
            feature_frames={"x": pd.DataFrame({"reliability": [0.5]}, index=[idx[-1]])},
            metric_health=pd.DataFrame({"available": [True]}),
            source_health=pd.DataFrame({"source": ["btc_price"], "available": [True]}),
            source_modes={"btc_price": "local_csv"},
        )

    @patch("risk_engine.web_publish.run_web_publish")
    def test_publish_web_v1_exits_on_validation_failure(self, mocked_publish) -> None:
        from risk_engine.web_publish import WebPublishResult

        mocked_publish.return_value = WebPublishResult(
            validation=ValidationResult(passed=False, errors=["bad"], warnings=[]),
            exported=False,
            export_result=None,
            sanity_report=pd.DataFrame(),
        )
        with self.assertRaises(SystemExit):
            runpy.run_path("publish_web_v1.py", run_name="__main__")

    @patch("risk_engine.validation.validate_output")
    @patch("risk_engine.validation.write_sanity_report")
    @patch("risk_engine.pipeline.run_pipeline")
    @patch("risk_engine.config.load_runtime_config")
    def test_validate_exits_nonzero_on_failed_validation(self, mocked_cfg, mocked_run, mocked_sanity, mocked_validate) -> None:
        mocked_cfg.return_value = type("Cfg", (), {"output_dir": Path.cwd() / "output"})()
        mocked_run.return_value = self._result()
        mocked_sanity.return_value = pd.DataFrame([{"passed": False}])
        mocked_validate.return_value = ValidationResult(passed=False, errors=["e"], warnings=[])
        with self.assertRaises(SystemExit):
            runpy.run_path("validate.py", run_name="__main__")


if __name__ == "__main__":
    unittest.main()
