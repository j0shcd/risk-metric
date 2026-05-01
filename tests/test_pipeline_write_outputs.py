import tempfile
import unittest
from pathlib import Path

import pandas as pd

from risk_engine.pipeline import write_outputs
from risk_engine.types import RiskOutput


class PipelineWriteOutputsTests(unittest.TestCase):
    def _result(self) -> RiskOutput:
        idx = pd.date_range("2026-01-01", periods=3, freq="D")
        series = pd.DataFrame({"btc_risk_heat": [0.1, 0.2, 0.3]}, index=idx)
        return RiskOutput(
            series=series,
            feature_frames={"metric_a": pd.DataFrame({"x": [1, 2, 3]}, index=idx)},
            metric_health=pd.DataFrame({"metric": ["a"], "available": [True]}),
            source_health=pd.DataFrame({"source": ["btc_price"], "available": [True]}),
            source_modes={"btc_price": "local_csv"},
            category_breakdowns={"btc": pd.DataFrame({"v": [1]}, index=[idx[-1]])},
            metric_breakdowns={"btc": pd.DataFrame({"v": [1]}, index=[idx[-1]])},
        )

    def test_write_outputs_creates_core_files_and_cleans_stale_feature_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            stale = outdir / "feature_frames"
            stale.mkdir(parents=True, exist_ok=True)
            (stale / "old.csv").write_text("x\n1\n", encoding="utf-8")

            write_outputs(self._result(), outdir)

            self.assertTrue((outdir / "risk_scores_full.csv").exists())
            self.assertTrue((outdir / "latest_scores.csv").exists())
            self.assertTrue((outdir / "feature_frames" / "metric_a.csv").exists())
            self.assertFalse((outdir / "feature_frames" / "old.csv").exists())
            self.assertTrue((outdir / "source_modes.csv").exists())


if __name__ == "__main__":
    unittest.main()
