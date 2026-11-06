from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from research.distribution_readout import mixture_forecasts, weighted_crps
from research.market_dataset import COMPONENTS, build_dataset, canonical_bytes, digest, load_snapshot, split_at
from research.market_scorecard import (
    baseline_candidates, create_campaign, score_candidate, submit_candidate, validate_candidate, verify_campaign,
)
from research.scorecard_artifacts import verify_packet


def snapshot(months=110):
    dates = pd.date_range("2000-01-01", pd.Timestamp("2000-01-01") + pd.DateOffset(months=months), freq="D")
    rng = np.random.default_rng(52)
    prices = np.exp(4 + np.cumsum(rng.normal(.0002, .012, len(dates))))
    monthly = pd.date_range("2001-01-31", dates[-1], freq="ME")
    return {"schema": "fixture", "availability": "synthetic", "daily": [
        {"date": date.date().isoformat(), "price": float(price)} for date, price in zip(dates, prices)],
        "monthly": [{"date": date.date().isoformat(), **{name: float(rng.uniform()) for name in COMPONENTS}}
                    for date in monthly]}


def write_source(path, data):
    frame = pd.DataFrame(data["daily"]).set_index("date").rename(columns={"price": "btc_price"})
    frame.index = pd.to_datetime(frame.index)
    # Daily baseline columns are intentionally present only at the monthly dates.
    for c in COMPONENTS:
        frame[c] = np.nan
    for row in data["monthly"]:
        for c in COMPONENTS:
            frame.loc[row["date"], c] = row[c]
    frame.to_csv(path)


class MarketScorecardTests(unittest.TestCase):
    def test_weighted_crps_matches_pairwise_definition_and_degenerate_forecast(self):
        x, w, y = np.array([-2., 0, 0, 3]), np.array([.1, .2, .3, .4]), .75
        expected = np.sum(w * abs(x-y)) - .5 * np.sum(w[:, None] * w[None, :] * abs(x[:, None]-x[None, :]))
        self.assertAlmostEqual(weighted_crps(x, w, y), expected)
        self.assertEqual(weighted_crps(np.array([2]), np.array([1]), -1), 3)
        with self.assertRaises(ValueError):
            weighted_crps(x, w * 2, y)

    def test_duplicate_context_and_empty_cells_preserve_reference(self):
        rng = np.random.default_rng(8)
        context = rng.normal(size=(24, 2))
        features = np.column_stack([context, context[:, 0]])
        forecast = mixture_forecasts(features, features, features[0])
        np.testing.assert_array_equal(forecast["reference"], forecast["candidate"])
        self.assertAlmostEqual(forecast["candidate"].sum(), 1)
        # Query shares a context cell but no indicator bin with calibration.
        calibration = features.copy()
        calibration[:, 2] = -100
        query = features[0].copy()
        query[2] = 100
        empty = mixture_forecasts(features, calibration, query)
        self.assertTrue(empty["candidate_fallback"])
        np.testing.assert_array_equal(empty["reference"], empty["candidate"])

    def test_entry_lag_calendar_horizon_and_distinct_downside_paths(self):
        dates = pd.date_range("2019-01-01", "2020-03-02", freq="D")
        data = {"daily": [{"date": d.date().isoformat(), "price": 100.} for d in dates],
                "monthly": [{"date": "2020-01-31", **{c: .5 for c in COMPONENTS}}]}
        # Price at decision is not the entry; after entry price doubles then drops.
        for row in data["daily"]:
            if row["date"] == "2020-01-31": row["price"] = 1000.
            if row["date"] == "2020-02-02": row["price"] = 200.
            if row["date"] == "2020-02-03": row["price"] = 80.
        result = build_dataset(data, [1])["rows"][0]["outcomes"]["1"]
        self.assertEqual(result["entry"], "2020-02-01")
        self.assertEqual(result["end"], "2020-03-01")
        np.testing.assert_allclose(result["values"], [0, np.log(100/80), np.log(200/80)])
        bad = deepcopy(data)
        next(r for r in bad["daily"] if r["date"] == "2020-02-03")["price"] = None
        self.assertEqual(build_dataset(bad, [1])["rows"][0]["outcomes"]["1"]["status"], "missing_price_path")
        for row in bad["daily"]:
            if row["date"] == "2020-02-03": row["price"] = 0
        self.assertIsNone(build_dataset(bad, [1])["rows"][0]["outcomes"]["1"]["values"])

    def test_no_partial_month_or_last_finite_value_carry(self):
        data = snapshot(30)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.csv"
            write_source(source, data)
            frozen = load_snapshot(source)
            self.assertLess(frozen["monthly"][-1]["date"], frozen["daily"][-1]["date"])
            frame = pd.read_csv(source, index_col=0)
            date = frozen["monthly"][-1]["date"]
            frame.loc[date, "dca_risk"] = np.nan
            frame.to_csv(source)
            self.assertIsNone(load_snapshot(source)["monthly"][-1]["dca_risk"])

    def test_maturity_is_strict_at_both_boundaries_and_48m_stays_unavailable(self):
        data = build_dataset(snapshot(145), [12, 24, 48])
        rows = data["rows"]
        found = False
        for i in range(len(rows)):
            fit, cal = split_at(rows, 12, i)
            if fit:
                found = True
                self.assertEqual(len(fit), 24)
                self.assertEqual(len(cal), 24)
                self.assertTrue(set(fit).isdisjoint(cal))
                self.assertLess(max(rows[j]["outcomes"]["12"]["available"] for j in fit), rows[cal[0]]["date"])
                self.assertLess(max(rows[j]["outcomes"]["12"]["available"] for j in cal), rows[i]["date"])
        self.assertTrue(found)
        self.assertTrue(all(not split_at(rows, 48, i)[0] for i in range(len(rows))))
        # A label available exactly at a cutoff is not yet admissible.
        fit, cal = split_at(rows, 12, len(rows)-1)
        changed = deepcopy(rows)
        changed[cal[-1]]["outcomes"]["12"]["available"] = rows[-1]["date"]
        self.assertNotIn(cal[-1], split_at(changed, 12, len(rows)-1)[1])

    def test_common_support_rejects_missing_fit_rows_extra_and_duplicate_dates(self):
        data = build_dataset(snapshot(), [12])
        candidate = baseline_candidates(data)[0]
        missing = deepcopy(candidate)
        missing["values"][0]["value"] = None
        with self.assertRaises(ValueError): validate_candidate(missing, data["rows"])
        duplicate = deepcopy(candidate)
        duplicate["values"][1]["date"] = duplicate["values"][0]["date"]
        with self.assertRaises(ValueError): validate_candidate(duplicate, data["rows"])
        extra = deepcopy(candidate)
        extra["values"].append({"date": "2099-01-31", "value": .2})
        with self.assertRaises(ValueError): validate_candidate(extra, data["rows"])

    def test_candidate_and_future_perturbations_do_not_change_frozen_earlier_forecasts(self):
        data = build_dataset(snapshot(), [12])
        candidate = baseline_candidates(data)[0]
        before = score_candidate(data, candidate)
        self.assertTrue(before["predictions"])
        cutoff = before["predictions"][0]["date"]
        altered = deepcopy(candidate)
        for row in altered["values"]:
            if row["date"] > cutoff: row["value"] = 1000-row["value"]
        changed_data = deepcopy(data)
        for row in changed_data["rows"]:
            if row["date"] > cutoff:
                row["context"] = [999., 999.]
                if row["outcomes"]["12"]["values"]:
                    row["outcomes"]["12"]["values"] = [999., 999., 999.]
        after = score_candidate(changed_data, altered)
        first = before["predictions"][0]
        second = after["predictions"][0]
        self.assertEqual(first, second)
        self.assertNotEqual(before["candidate_id"], after["candidate_id"])
        self.assertEqual(digest(data), before["dataset_id"])

    def test_price_scale_does_not_change_outcomes_or_scores(self):
        source = snapshot()
        scaled = deepcopy(source)
        for row in scaled["daily"]: row["price"] *= 777.
        left, right = build_dataset(source, [12]), build_dataset(scaled, [12])
        a = score_candidate(left, baseline_candidates(left)[0])
        b = score_candidate(right, baseline_candidates(right)[0])
        for l, r in zip(a["cells"], b["cells"]):
            self.assertEqual(l["forecast_origins_id"], r["forecast_origins_id"])
            self.assertAlmostEqual(l["candidate_mean_crps"], r["candidate_mean_crps"])
            self.assertAlmostEqual(l["ordinal_alignment"], r["ordinal_alignment"])

    def test_campaign_replay_tampering_budget_and_failed_attempts(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory).resolve()
            source, campaign = directory / "source.csv", directory / "campaign"
            write_source(source, snapshot(45))
            identity = create_campaign(source, campaign, [12, 48])
            manifest, data = verify_campaign(campaign)
            self.assertEqual(identity, manifest)
            baseline = (campaign / "baseline.json").read_bytes()
            candidate = baseline_candidates(data)[0]
            result = submit_candidate(campaign, canonical_bytes(candidate))
            self.assertEqual(result["attempt"], "attempt-001")
            self.assertEqual((campaign / "baseline.json").read_bytes(), baseline)
            self.assertEqual(result["cells"][3]["forecast_status"], "insufficient_evidence")
            self.assertEqual(submit_candidate(campaign, b"invalid")["status"], "ineligible")
            # Interrupted slots consume budget, including the absence of receipts.
            for i in range(3, 25): (campaign / "attempts" / f"attempt-{i:03d}").mkdir()
            with self.assertRaisesRegex(ValueError, "budget exhausted"): submit_candidate(campaign, b"invalid")
            with self.assertRaises(FileExistsError): create_campaign(source, campaign, [12])
            with patch("research.market_scorecard.code_hashes", return_value={}):
                with self.assertRaisesRegex(ValueError, "code changed"): verify_campaign(campaign)
            with patch("research.market_scorecard.runtime", return_value={}):
                with self.assertRaisesRegex(ValueError, "runtime changed"): verify_campaign(campaign)
            (campaign / "attempts/attempt-001/submitted.json").write_bytes(b"{}")
            with self.assertRaisesRegex(ValueError, "corrupt.*submitted"): verify_campaign(campaign)

    def test_concurrent_reservations_are_bounded_and_receipts_cannot_move_slots(self):
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory).resolve()
            source, campaign = directory / "source.csv", directory / "campaign"
            write_source(source, snapshot(24))
            create_campaign(source, campaign, [12])
            def attempt(_):
                try:
                    return submit_candidate(campaign, b"{}")
                except ValueError as error:
                    self.assertIn("budget exhausted", str(error))
                    return None
            with ThreadPoolExecutor(max_workers=4) as executor:
                results = list(executor.map(attempt, range(28)))
            slots = [r["attempt"] for r in results if r is not None]
            self.assertEqual(len(slots), 24)
            self.assertEqual(len(set(slots)), 24)
            verify_campaign(campaign)
            transplant = directory / "transplant"
            create_campaign(source, transplant, [24])
            shutil.copytree(campaign / "attempts/attempt-001", transplant / "attempts/attempt-001")
            with self.assertRaisesRegex(ValueError, "another campaign"): verify_campaign(transplant)

    def test_interrupted_and_symlinked_receipts_are_never_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory).resolve()
            source, campaign = directory / "source.csv", directory / "campaign"
            write_source(source, snapshot(45))
            create_campaign(source, campaign, [12])
            with patch("research.market_scorecard.write_packet", side_effect=OSError("interruption")):
                with self.assertRaises(OSError): submit_candidate(campaign, b"{}")
            attempt = campaign / "attempts/attempt-001"
            self.assertTrue((attempt / "submitted.json").exists())
            with self.assertRaisesRegex(ValueError, "incomplete"): verify_packet(attempt)
            link = directory / "link"
            link.symlink_to(campaign, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"): verify_campaign(link)
            (campaign / "baseline.json").write_bytes(b"{}")
            with self.assertRaisesRegex(ValueError, "corrupt"): verify_campaign(campaign)


if __name__ == "__main__":
    unittest.main()
