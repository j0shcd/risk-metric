import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from risk_engine.config import RuntimeConfig
from risk_engine.types import RiskOutput
from risk_engine.validation import ValidationResult
from risk_engine.web_publish import run_web_publish


class WebPublishTests(unittest.TestCase):
    def _cfg(self, root: Path) -> RuntimeConfig:
        return RuntimeConfig(
            project_root=root,
            data_dir=root / "data",
            output_dir=root / "output",
            cache_dir=root / "data",
        )

    def _sample_result(self) -> RiskOutput:
        index = pd.to_datetime(["2026-04-23", "2026-04-24"])
        series = pd.DataFrame(
            {
                "btc_risk_heat": [0.2, 0.3],
                "btc_risk_attention": [0.4, 0.5],
                "total_market_risk_heat": [0.1, 0.2],
                "total_market_risk_attention": [0.3, 0.4],
                "headline_attention": [0.36, 0.43],
                "headline_heat": [0.17, 0.24],
                "confidence_score": [0.65, 0.7],
                "btc_risk_confidence": [0.7, 0.8],
                "total_market_risk_confidence": [0.55, 0.6],
                "btc_risk_coverage": [0.5, 0.55],
                "total_market_risk_coverage": [0.45, 0.5],
                "btc_price": [70000.0, 71000.0],
                "total_market_cap": [2.5e12, 2.55e12],
            },
            index=index,
        )
        return RiskOutput(
            series=series,
            feature_frames={"x": pd.DataFrame({"reliability": [0.5]}, index=[index[-1]])},
            metric_health=pd.DataFrame({"target": ["btc", "total_market"], "available": [True, True]}),
            source_health=pd.DataFrame({"source": ["btc_price"], "available": [True]}),
            source_modes={"btc_price": "local_csv"},
            category_breakdowns={"btc": pd.DataFrame(index=index), "total_market": pd.DataFrame(index=index)},
            metric_breakdowns={"btc": pd.DataFrame(index=index), "total_market": pd.DataFrame(index=index)},
        )

    @patch("risk_engine.web_publish.export_web_v1")
    @patch("risk_engine.web_publish.validate_output")
    @patch("risk_engine.web_publish.write_sanity_report")
    @patch("risk_engine.web_publish.write_outputs")
    @patch("risk_engine.web_publish.run_pipeline")
    def test_publish_exports_when_validation_has_only_warnings(
        self,
        mocked_run,
        mocked_write_outputs,
        mocked_sanity,
        mocked_validate,
        mocked_export,
    ) -> None:
        mocked_run.return_value = self._sample_result()
        mocked_sanity.return_value = pd.DataFrame([{"check": "x", "passed": True}])
        mocked_validate.return_value = ValidationResult(passed=True, errors=[], warnings=["warn"])

        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg = self._cfg(Path(tmp_dir))
            result = run_web_publish(cfg)

        self.assertTrue(result.validation.passed)
        self.assertTrue(result.exported)
        mocked_write_outputs.assert_called_once()
        mocked_export.assert_called_once()

    @patch("risk_engine.web_publish.export_web_v1")
    @patch("risk_engine.web_publish.validate_output")
    @patch("risk_engine.web_publish.write_sanity_report")
    @patch("risk_engine.web_publish.write_outputs")
    @patch("risk_engine.web_publish.run_pipeline")
    def test_publish_blocks_export_on_hard_validation_failure(
        self,
        mocked_run,
        mocked_write_outputs,
        mocked_sanity,
        mocked_validate,
        mocked_export,
    ) -> None:
        mocked_run.return_value = self._sample_result()
        mocked_sanity.return_value = pd.DataFrame([{"check": "x", "passed": False}])
        mocked_validate.return_value = ValidationResult(
            passed=False,
            errors=["missing required column"],
            warnings=["warn"],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg = self._cfg(Path(tmp_dir))
            result = run_web_publish(cfg)

        self.assertFalse(result.validation.passed)
        self.assertFalse(result.exported)
        mocked_write_outputs.assert_called_once()
        mocked_export.assert_not_called()


if __name__ == "__main__":
    unittest.main()
