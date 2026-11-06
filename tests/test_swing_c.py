import unittest
import numpy as np
import pandas as pd
from research.candidates.swing_c.generate import generate


class PathAsymmetryTests(unittest.TestCase):
    def test_future_suffix_cannot_change_past(self):
        dates = pd.date_range('2010-01-01', '2020-12-31')
        prices = pd.Series(np.exp(5 + np.sin(np.arange(len(dates))/75) + np.arange(len(dates))/1000), index=dates)
        cutoff = pd.Timestamp('2016-06-30')
        original = generate(prices.loc[:cutoff])
        prices.loc[prices.index > cutoff] *= 100
        pd.testing.assert_series_equal(original, generate(prices).loc[:cutoff])

    def test_incomplete_month_does_not_emit_future_date(self):
        prices = pd.Series(10., index=pd.date_range('2010-01-01', '2010-03-15'))
        self.assertEqual(generate(prices).index.max(), pd.Timestamp('2010-02-28'))

    def test_direction_scale_and_finite_neutral(self):
        dates = pd.date_range('2010-01-31', periods=40, freq='ME')
        rising = pd.Series(np.exp(np.arange(40)/10), index=dates)
        self.assertEqual(generate(rising).iloc[-1], 100)
        self.assertEqual(generate(1/rising).iloc[-1], 0)
        self.assertTrue((generate(rising*123)-generate(rising)).abs().max() < 1e-10)
        self.assertTrue((generate(rising*0+5) == 50).all())

    def test_invalid_prices_rejected(self):
        with self.assertRaises(ValueError):
            generate(pd.Series([1, 0], index=pd.date_range('2010-01-01', periods=2)))

if __name__ == '__main__':
    unittest.main()
