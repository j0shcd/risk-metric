from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from research.market_dataset import COMPONENTS, build_dataset
from research.market_information import baseline_candidates, score_candidate


def snapshot(months=110):
    dates = pd.date_range("2000-01-01", pd.Timestamp("2000-01-01") + pd.DateOffset(months=months), freq="D")
    rng = np.random.default_rng(971)
    prices = np.exp(4 + np.cumsum(rng.normal(.0002, .012, len(dates))))
    monthly = pd.date_range("2001-01-31", dates[-1], freq="ME")
    return {"schema": "fixture", "daily": [
        {"date": d.date().isoformat(), "price": float(p)} for d, p in zip(dates, prices)],
        "monthly": [{"date": d.date().isoformat(), **{c: float(rng.uniform()) for c in COMPONENTS}}
                    for d in monthly]}


def cell(result, horizon, role, target="terminal_log_return"):
    return next(c for c in result["cells"] if (c["horizon"], c["role"], c["target"]) == (horizon, role, target))


class MarketInformationTests(unittest.TestCase):
    def setUp(self):
        self.source = snapshot()
        self.candidate = baseline_candidates(self.source)[0]

    def test_single_mature_pool_fits_density_and_crps_matches_independent_formula(self):
        result = score_candidate(self.source, self.candidate, [12])
        first = result["predictions"][0]
        rows = build_dataset(self.source, [12])["rows"]
        by_date = {r["date"]: r for r in rows}
        # No second fitting/calibration pool or second horizon delay is required.
        self.assertEqual(first["train_dates"], [r["date"] for r in rows[:24]])
        expected_query = next(r for r in rows if sum(
            p["date"] < r["date"] and p["outcomes"]["12"]["status"] == "complete"
            and p["outcomes"]["12"]["available"] < r["date"] for p in rows) >= 24)
        self.assertEqual(first["date"], expected_query["date"])
        candidate_values = {r["date"]: r["value"] for r in self.candidate["values"]}
        training_features = [[*by_date[d]["context"], candidate_values[d]] for d in first["train_dates"]]
        np.testing.assert_array_equal(first["thresholds"], np.median(training_features, axis=0))
        for record in result["predictions"]:
            self.assertEqual(len(record["train_dates"]), 24)
            self.assertLess(record["train_last_label_available"], record["date"])
            self.assertTrue(all(d < record["date"] for d in record["train_dates"]))
            admissible = [r["date"] for r in rows if r["date"] < record["date"]
                          and r["outcomes"]["12"]["status"] == "complete"
                          and r["outcomes"]["12"]["available"] < record["date"]]
            self.assertEqual(record["train_dates"], admissible[-24:])
            expected_atoms = [by_date[d]["outcomes"]["12"]["values"][
                ("terminal_log_return", "entry_adverse_log_loss", "peak_drawdown_log_loss").index(record["target"])]
                for d in record["train_dates"]]
            np.testing.assert_array_equal(record["atoms"], expected_atoms)
            if record["status"] == "scored":
                x, y = np.array(record["atoms"]), record["outcome"]
                unconditional = np.mean(abs(x-y))-.5*np.mean(abs(x[:, None]-x[None, :]))
                self.assertAlmostEqual(record["unconditional_crps"], unconditional, places=12)
                for name in ("reference", "candidate"):
                    w = np.array(record[name + "_weights"])
                    expected = np.sum(w * abs(x-y)) - .5 * np.sum(w[:, None] * w[None, :] * abs(x[:, None]-x[None, :]))
                    self.assertAlmostEqual(record[name + "_crps"], expected, places=12)
        json.dumps(result, allow_nan=False)

    def test_label_available_exactly_at_query_is_not_training_data(self):
        data = build_dataset(self.source, [12])
        before = score_candidate(self.source, self.candidate, [12])
        first = before["predictions"][0]
        altered = deepcopy(data)
        by_date = {r["date"]: r for r in altered["rows"]}
        by_date[first["train_dates"][-1]]["outcomes"]["12"]["available"] = first["date"]
        with patch("research.market_information.build_dataset", return_value=altered):
            after = score_candidate(self.source, self.candidate, [12])
        self.assertFalse(next(r for r in after["eligibility"] if r["date"] == first["date"])["forecast_available"])
        self.assertNotEqual(after["predictions"][0]["date"], first["date"])

    def test_complete_price_path_does_not_score_unpublished_label_and_pending_forecasts_remain(self):
        result = score_candidate(self.source, self.candidate, [1])
        as_of = self.source["daily"][-1]["date"]  # 2009-03-01, endpoint present but label next day.
        records = [r for r in result["predictions"] if r["end"] == as_of]
        self.assertTrue(records)
        for record in records:
            self.assertEqual(record["outcome_status"], "complete")
            self.assertGreater(record["label_available"], as_of)
            self.assertEqual(record["role"], "pending")
            self.assertEqual(record["status"], "reconstruction_pending")
            self.assertIn("not_prospective", record["forecast_origin_kind"])
            for field in ("outcome", "candidate_crps", "reference_crps", "loss_improvement"):
                self.assertIsNone(record[field])
            self.assertEqual(len(record["atoms"]), 24)
        self.assertGreater(cell(result, 1, "pending")["forecast_n"], 0)
        self.assertEqual(cell(result, 1, "pending")["scored_n"], 0)

    def test_future_price_and_feature_suffix_cannot_change_earlier_distributions(self):
        before = score_candidate(self.source, self.candidate, [12])
        cutoff = before["predictions"][9]["date"]
        changed_source, changed_candidate = deepcopy(self.source), deepcopy(self.candidate)
        for row in changed_source["daily"]:
            if row["date"] > cutoff:
                row["price"] *= 17
        for row in changed_candidate["values"]:
            if row["date"] > cutoff:
                row["value"] += 100
        after = score_candidate(changed_source, changed_candidate, [12])
        fields = ("date", "horizon", "target", "train_dates", "train_last_label_available", "atoms",
                  "thresholds", "reference_weights", "candidate_weights", "context_cell_n", "candidate_cell_n")
        left = [{k: r[k] for k in fields} for r in before["predictions"] if r["date"] <= cutoff]
        right = [{k: r[k] for k in fields} for r in after["predictions"] if r["date"] <= cutoff]
        self.assertTrue(left)
        self.assertEqual(left, right)
        self.assertNotEqual(before["candidate_id"], after["candidate_id"])

    def test_constants_and_exact_context_duplicates_do_not_change_forecast_or_loss(self):
        data = build_dataset(self.source, [12])
        for feature in (None, 0, 1):
            candidate = deepcopy(self.candidate)
            candidate["values"] = [{"date": r["date"], "value": .2 if feature is None else r["context"][feature]}
                                   for r in data["rows"]]
            result = score_candidate(self.source, candidate, [12])
            for record in result["predictions"]:
                self.assertEqual(record["reference_weights"], record["candidate_weights"])
                self.assertEqual(record["reference_crps"], record["candidate_crps"])

    def test_missing_candidate_support_is_rejected_without_favourable_date_filter(self):
        for variation in ("missing", "duplicate", "nonfinite", "null"):
            candidate = deepcopy(self.candidate)
            if variation == "missing": candidate["values"].pop()
            if variation == "duplicate": candidate["values"][1]["date"] = candidate["values"][0]["date"]
            if variation == "nonfinite": candidate["values"][0]["value"] = float("nan")
            if variation == "null": candidate["values"][0]["value"] = None
            with self.subTest(variation=variation), self.assertRaises(ValueError):
                score_candidate(self.source, candidate, [12])

    def test_roles_use_label_availability_and_query_date_separately(self):
        result = score_candidate(self.source, self.candidate, [12], development_cutoff="2005-12-31", outer_start="2007-01-01")
        self.assertGreater(cell(result, 12, "development")["scored_n"], 0)
        self.assertGreater(cell(result, 12, "retrospective_challenge")["scored_n"], 0)
        self.assertGreater(cell(result, 12, "outer")["scored_n"], 0)
        for record in result["predictions"]:
            if record["status"] != "scored": continue
            if record["role"] == "development":
                self.assertLessEqual(record["label_available"], "2005-12-31")
            elif record["role"] == "outer":
                self.assertGreaterEqual(record["date"], "2007-01-01")
                self.assertLessEqual(record["label_available"], result["as_of"])
            else:
                self.assertGreater(record["label_available"], "2005-12-31")
                self.assertLess(record["date"], "2007-01-01")
        undirected = deepcopy(self.candidate)
        undirected["direction"] = "undirected"
        self.assertTrue(all(c["ordinal_alignment"] is None for c in score_candidate(self.source, undirected, [12])["cells"]))

    def test_ordinal_alignment_keeps_advertised_return_and_loss_directions_separate(self):
        data = build_dataset(self.source, [1])
        for target_index, target in enumerate(("terminal_log_return", "entry_adverse_log_loss", "peak_drawdown_log_loss")):
            # Outcome-derived values are a synthetic sign test, not a causal candidate.
            candidate = deepcopy(self.candidate)
            candidate["values"] = [{"date": row["date"], "value": (
                (-1 if target_index == 0 else 1) * row["outcomes"]["1"]["values"][target_index]
                if row["outcomes"]["1"]["status"] == "complete" else 0.)} for row in data["rows"]]
            result = score_candidate(self.source, candidate, [1])
            self.assertAlmostEqual(cell(result, 1, "development", target)["ordinal_alignment"], 1.)

    def test_price_time_baselines_are_prefix_stable_and_do_not_fill_missing_prices(self):
        before = baseline_candidates(self.source)
        changed = deepcopy(self.source)
        cutoff = changed["monthly"][30]["date"]
        for row in changed["daily"]:
            if row["date"] > cutoff: row["price"] *= 10000
        after = baseline_candidates(changed)
        self.assertEqual([c["name"] for c in before], [c["name"] for c in after])
        for left, right in zip(before, after):
            self.assertEqual([v for v in left["values"] if v["date"] <= cutoff],
                             [v for v in right["values"] if v["date"] <= cutoff])
        missing = deepcopy(self.source)
        missing["daily"][-40]["price"] = None
        baselines = {c["name"]: c for c in baseline_candidates(missing)}
        self.assertIsNone(baselines["price_ath_drawdown"]["values"][-1]["value"])
        self.assertIsNone(baselines["price_log_sma_200d"]["values"][-1]["value"])
        self.assertTrue(all(len(c["values"]) == len(self.source["monthly"]) for c in before))

    def test_committed_market_snapshot_coverage_roles_and_common_support(self):
        path = Path(__file__).resolve().parents[1] / "docs/artifacts/market-scorecard-2026-11-06-snapshot.json"
        source = json.loads(path.read_text())
        baselines = baseline_candidates(source)
        incumbent = score_candidate(source, baselines[0])
        price = score_candidate(source, next(c for c in baselines if c["name"] == "price_trend_12m"))
        self.assertEqual(len(source["monthly"]), 139)
        for horizon, development, outer, challenge in ((12, 48, 30, 13), (24, 24, 18, 25), (48, 0, 0, 19)):
            for role, expected in (("development", development), ("outer", outer), ("retrospective_challenge", challenge)):
                self.assertEqual(cell(incumbent, horizon, role)["scored_n"], expected)
            self.assertGreater(cell(incumbent, horizon, "pending")["forecast_n"], 0)
        self.assertEqual(cell(incumbent, 48, "development")["forecast_status"], "insufficient_evidence")
        for left, right in zip(incumbent["cells"], price["cells"]):
            self.assertEqual(left["forecast_origins_id"], right["forecast_origins_id"])
            self.assertEqual(left["scored_origins_id"], right["scored_origins_id"])
            self.assertEqual(left["reference_mean_crps"], right["reference_mean_crps"])
        for record in price["predictions"]:
            self.assertEqual(record["reference_weights"], record["candidate_weights"])
        json.dumps(incumbent, allow_nan=False)

    def test_invalid_configuration_fails_before_replay(self):
        for arguments in ({"minimum": 0}, {"minimum": True}, {"development_cutoff": "2022-12-31", "outer_start": "2022-12-31"},
                          {"development_cutoff": "2022-12-31T12:00"}, {"horizons": []}):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                score_candidate(self.source, self.candidate, **arguments)


if __name__ == "__main__":
    unittest.main()
