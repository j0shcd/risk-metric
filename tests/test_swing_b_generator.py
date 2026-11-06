import unittest
import numpy as np
import pandas as pd
from research.candidates.swing_b.generator import generate, monthly_prices

class SwingBTests(unittest.TestCase):
    def setUp(self):
        self.frame = pd.DataFrame({'Date': pd.date_range('2012-01-01','2022-12-31'), 'Price': np.exp(np.linspace(0, 5, 4018) + .8 * np.sin(np.arange(4018) / 190.))})

    def test_future_suffix_and_truncation(self):
        full = generate(self.frame)
        for cutoff in ['2014-06-30','2017-03-19','2020-12-31']:
            prefix = self.frame[self.frame.Date <= cutoff]
            expected = generate(prefix)
            pd.testing.assert_frame_equal(expected, full.loc[expected.index])
            changed = self.frame.copy()
            changed.loc[changed.Date > cutoff, 'Price'] *= 1e12
            pd.testing.assert_frame_equal(expected, generate(changed).loc[expected.index])

    def test_scale_invariance_and_finite(self):
        scores = generate(self.frame)
        scaled = self.frame.copy()
        scaled.Price *= 1000
        np.testing.assert_allclose(scores, generate(scaled), atol=1e-10)
        self.assertTrue(np.isfinite(scores).all().all())
        self.assertTrue(((scores >= 0) & (scores <= 100)).all().all())

    def test_current_shock_has_risk_direction(self):
        frame = self.frame[self.frame.Date <= '2020-12-31'].copy()
        original = generate(frame).iloc[-1]
        frame.loc[frame.index[-1], 'Price'] *= 2
        self.assertTrue((generate(frame).iloc[-1] > original).all())

    def test_invalid_data_and_partial_month(self):
        frame = self.frame[self.frame.Date <= '2020-12-15'].copy()
        self.assertEqual(monthly_prices(frame).index[-1], pd.Timestamp('2020-11-30'))
        frame.loc[frame.index[-1], 'Price'] = 0
        with self.assertRaises(ValueError):
            generate(frame)
        with self.assertRaises(ValueError):
            generate(pd.concat([self.frame, self.frame.iloc[:1]]))

if __name__ == '__main__':
    unittest.main()
