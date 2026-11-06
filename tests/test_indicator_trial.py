from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from research.indicator_trial import main, run_trial
from research.market_dataset import load_snapshot
from research.scorecard_artifacts import verify_packet
from tests.test_market_scorecard import snapshot, write_source


class IndicatorTrialTests(unittest.TestCase):
    def fixture(self, directory):
        bundle = directory/"bundle"; bundle.mkdir()
        source = bundle/"development_scores.csv"
        write_source(source, snapshot(110))
        manifest = {"cutoff": "2022-12-31", "sources": {source.name: {"development_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}}}
        (bundle/"manifest.json").write_text(json.dumps(manifest))
        data = load_snapshot(source)
        candidate = directory/"candidate.csv"
        pd.DataFrame({"Date": [r["date"] for r in data["monthly"]], "signal": [r["dca_risk"] for r in data["monthly"]]}).to_csv(candidate, index=False)
        return bundle, candidate

    def test_common_development_support_and_unconditional_baseline(self):
        with tempfile.TemporaryDirectory() as raw:
            bundle, candidate = self.fixture(Path(raw))
            trial = run_trial(bundle, candidate, "signal", "fixture", "synthetic unit fixture")
            result = trial["result"]
            self.assertTrue(all(c["role"] == "development" for r in trial["references"] for c in r["cells"]))
            self.assertEqual(len(trial["references"]), 13)
            incumbent = next(r for r in trial["references"] if r["name"] == "dca_risk")
            for cell in incumbent["cells"]:
                ours = next(c for c in result["cells"] if (c["role"], c["horizon"], c["target"]) == (cell["role"], cell["horizon"], cell["target"]))
                self.assertEqual(ours["candidate_mean_crps"], cell["candidate_mean_crps"])
                self.assertEqual(ours["unconditional_mean_crps"], cell["unconditional_mean_crps"])

    def test_hash_mismatch_missing_dates_and_postcutoff_inputs_fail_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            bundle, candidate = self.fixture(Path(raw))
            frame = pd.read_csv(candidate)
            frame.iloc[1:].to_csv(candidate, index=False)
            with self.assertRaisesRegex(ValueError, "entire frozen"): run_trial(bundle, candidate, "signal", "x", "x")
            frame.loc[len(frame)] = ["2023-01-31", .5]
            frame.to_csv(candidate, index=False)
            with self.assertRaisesRegex(ValueError, "completed month"): run_trial(bundle, candidate, "signal", "x", "x")
            manifest = json.loads((bundle/"manifest.json").read_text())
            manifest["sources"]["development_scores.csv"]["development_sha256"] = "changed"
            (bundle/"manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "cutoff/hash"): run_trial(bundle, candidate, "signal", "x", "x")

    def test_cli_writes_exclusive_replayable_receipt(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw).resolve()
            bundle, candidate = self.fixture(directory)
            target = directory/"attempt"
            args = ["--bundle", str(bundle), "--candidate-csv", str(candidate), "--column", "signal", "--name", "fixture",
                    "--provenance", "synthetic unit fixture", "--output-dir", str(target)]
            with redirect_stdout(io.StringIO()): self.assertEqual(main(args), 0)
            verify_packet(target)
            self.assertTrue((target/"report.md").exists())
            with self.assertRaises(FileExistsError): main(args)


if __name__ == "__main__":
    unittest.main()
