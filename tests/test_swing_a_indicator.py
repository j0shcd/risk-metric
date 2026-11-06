import unittest

import numpy as np
import pandas as pd

from research.candidates.swing_a.indicator import generate_indicator


class SwingACausalityTests(unittest.TestCase):
    def setUp(self):
        dates = pd.date_range("2010-01-01", periods=1500)
        self.frame = pd.DataFrame({"Date": dates, "Price": np.exp(np.linspace(1, 5, len(dates)) + np.sin(np.arange(len(dates))/80))})
        self.queries = pd.date_range("2010-01-31", "2014-01-31", freq="ME")

    def test_every_month_prefix_equals_full_history(self):
        full = generate_indicator(self.frame, self.queries)
        for day in self.queries:
            prefix = self.frame[self.frame.Date <= day]
            self.assertAlmostEqual(full.loc[day], generate_indicator(prefix, [day]).iloc[0], places=14)

    def test_future_prices_cannot_change_earlier_scores(self):
        cutoff = pd.Timestamp("2012-01-31")
        changed = self.frame.copy()
        changed.loc[changed.Date >= cutoff, "Price"] *= 1e8
        before = self.queries[self.queries <= cutoff]
        pd.testing.assert_series_equal(generate_indicator(self.frame, before), generate_indicator(changed, before))

    def test_scale_invariant_and_bounded(self):
        scaled = self.frame.copy()
        scaled.Price *= 1000
        first = generate_indicator(self.frame, self.queries)
        np.testing.assert_allclose(first, generate_indicator(scaled, self.queries), atol=1e-13)
        self.assertTrue(first.between(0, 1).all())

    def test_reject_duplicate_invalid_input(self):
        with self.assertRaises(ValueError):
            generate_indicator(pd.concat([self.frame, self.frame.iloc[:1]]), self.queries)
        broken = self.frame.copy()
        broken.loc[0, "Price"] = 0
        with self.assertRaises(ValueError):
            generate_indicator(broken, self.queries)

    def test_empty_history_is_neutral(self):
        result = generate_indicator(self.frame.iloc[:0], self.queries)
        self.assertTrue((result == 0.5).all())


if __name__ == "__main__":
    unittest.main()
