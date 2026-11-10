import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location("readout_checker", Path(__file__).resolve().parents[1]/"scripts/check-target-readout-study.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class ReadoutCheckerTests(unittest.TestCase):
    def record(self):
        return {"kind": "gaussian", "mean": 0., "sigma": 1., "outcome": 0.,
                "risk": .5, "lo80": -1., "hi80": 1.,
                "crps": (math.sqrt(2)-1)/math.sqrt(math.pi), "brier": .25,
                "coverage80": 1, "width80": 2., "method": "gaussian_expanding",
                "date": "2024-01-31", "cal_last_label_available": "2024-01-01",
                "fit_last_label_available": "2022-01-01", "cal_first_origin": "2022-01-31",
                "train_indices": [0, 1], "cal_indices": [9, 10]}

    def test_rescoring_rejects_corrupt_losses_and_unavailable_labels(self):
        checker.scores(self.record())
        for key, value in (("crps", 0.), ("risk", .9),
                           ("cal_last_label_available", "2024-02-01"),
                           ("fit_last_label_available", "2022-02-01")):
            record = self.record()
            record[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                checker.scores(record)

    def test_fallback_and_terminal_deployment_have_known_unit_balances(self):
        prices = list(range(1, 49))
        fixed, wait, sweep = checker.balance(prices, [None]*48, [True]*48)
        self.assertAlmostEqual(fixed, .998*sum(1/p for p in prices))
        self.assertEqual((wait, sweep), (0, 0))
        delayed, wait, sweep = checker.balance(prices, [1.]*48, [False]*48)
        self.assertAlmostEqual(delayed, .998)
        self.assertEqual((wait, sweep), (23.5, 1.))

    def test_hash_failure_precedes_parsing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/"summary.json").write_text(json.dumps({"failures": [], "network_attempts": [],
                "completed_world_law_jobs": 96, "output_sha256": {"broken.json": "0"*64}}))
            (root/"broken.json").write_bytes(b"not json")
            with self.assertRaisesRegex(ValueError, "output hash mismatch"):
                checker.check(root)


if __name__ == "__main__":
    unittest.main()
