from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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

    def captured_input_trial(self, directory, replace_source=False, replace_candidate=False):
        bundle, candidate = self.fixture(directory)
        source = bundle/"development_scores.csv"
        source_bytes, candidate_bytes = source.read_bytes(), candidate.read_bytes()
        expected_snapshot = load_snapshot(source)
        expected_candidate = pd.read_csv(io.BytesIO(candidate_bytes))
        changed_source = pd.read_csv(io.BytesIO(source_bytes))
        changed_source["btc_price"] *= 2
        changed_candidate = expected_candidate.copy()
        changed_candidate["signal"] += .125
        replacements = {}
        if replace_source:
            replacements[source] = changed_source.to_csv(index=False).encode()
        if replace_candidate:
            replacements[candidate] = changed_candidate.to_csv(index=False).encode()
        original_read = Path.read_bytes
        captured = {}
        def replace_after_capture(path):
            payload = original_read(path)
            if path in replacements:
                path.write_bytes(replacements.pop(path))
            return payload
        def score(snapshot, submitted):
            captured.update(snapshot=snapshot, submitted=submitted)
            return {"dataset_id": "fixture", "code_sha256": {}, "source_sha256": snapshot["source_sha256"]}
        with patch.object(Path, "read_bytes", replace_after_capture), patch("research.indicator_trial.score_candidate", score), patch("research.indicator_trial.baseline_candidates", return_value=[]):
            trial = run_trial(bundle, candidate, "signal", "fixture", "synthetic captured-input regression")
        self.assertEqual(captured["snapshot"]["source_sha256"], expected_snapshot["source_sha256"])
        self.assertTrue(captured["snapshot"] == expected_snapshot, "captured snapshot differs")
        self.assertEqual(trial["result"]["source_sha256"], hashlib.sha256(source_bytes).hexdigest())
        self.assertEqual(trial["candidate_csv_sha256"], hashlib.sha256(candidate_bytes).hexdigest())
        self.assertEqual([v["value"] for v in captured["submitted"]["values"]], expected_candidate["signal"].tolist())
        self.assertFalse(replacements)

    def test_replaced_source_path_cannot_change_captured_snapshot(self):
        with tempfile.TemporaryDirectory() as raw:
            self.captured_input_trial(Path(raw), replace_source=True)

    def test_replaced_candidate_path_cannot_change_captured_values(self):
        with tempfile.TemporaryDirectory() as raw:
            self.captured_input_trial(Path(raw), replace_candidate=True)

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
