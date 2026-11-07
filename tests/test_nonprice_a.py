import unittest
import numpy as np
import pandas as pd
from research.candidates.nonprice_a.generator import generate


class AttentionTests(unittest.TestCase):
    def setUp(self):
        self.frame = pd.DataFrame({"Date": pd.date_range("2010-01-01", periods=900),
                                   "wikipedia_pageviews": np.arange(900) + 100})
        self.query = self.frame.Date.iloc[700]

    def test_independent_window_and_lag(self):
        f = self.frame.copy()
        f.loc[:, "wikipedia_pageviews"] = 10
        f.loc[669:698, "wikipedia_pageviews"] = 30
        f.loc[699:, "wikipedia_pageviews"] = 999999
        out = generate(f, [self.query]).iloc[0]
        self.assertAlmostEqual(out.attention_surge_risk, .75)
        self.assertTrue(out.available)

    def test_exact_safe_count_domain(self):
        for count, available in [(2**53 - 1, True), (2**53, False), (1e308, False)]:
            frame = self.frame.copy()
            frame["wikipedia_pageviews"] = float(count)
            row = generate(frame, [self.query]).iloc[0]
            self.assertTrue(np.isfinite(row.attention_surge_risk))
            self.assertEqual(row.attention_surge_risk, .5)
            self.assertEqual(row.available, available)
            self.assertEqual(row.valid_days, 395 if available else 0)

    def test_prefix_and_poisoned_future(self):
        queries = self.frame.Date.iloc[[400, 500, 700]]
        full = generate(self.frame, queries)
        prefix = generate(self.frame.iloc[:701], queries)
        pd.testing.assert_frame_equal(full, prefix)
        poison = self.frame.astype({"wikipedia_pageviews": object})
        poison.loc[699:, "wikipedia_pageviews"] = "future poison"
        pd.testing.assert_frame_equal(full, generate(poison, queries))
        for n, q in enumerate(queries):
            pd.testing.assert_frame_equal(full.iloc[[n]].reset_index(drop=True),
                generate(self.frame[self.frame.Date <= q], [q]))

    def test_domains_missing_zero_and_scale(self):
        expected = generate(self.frame, [self.query])
        scaled = self.frame.copy(); scaled.wikipedia_pageviews *= 17
        pd.testing.assert_frame_equal(expected, generate(scaled, [self.query]))
        for bad in [np.nan, np.inf, -1, 1.5, "bad"]:
            frame = self.frame.astype({"wikipedia_pageviews": object})
            frame.loc[500, "wikipedia_pageviews"] = bad
            row = generate(frame, [self.query]).iloc[0]
            self.assertEqual(row.attention_surge_risk, .5)
            self.assertFalse(row.available)
        zero = self.frame.copy(); zero.wikipedia_pageviews = 0
        self.assertEqual(generate(zero, [self.query]).iloc[0].status, "zero_baseline")
        row = generate(self.frame.iloc[:50], [self.query]).iloc[0]
        self.assertEqual(row.attention_surge_risk, .5)
        self.assertFalse(row.available)
        with self.assertRaises(ValueError):
            generate(pd.concat([self.frame, self.frame.iloc[:1]]), [self.query])


if __name__ == "__main__":
    unittest.main()
