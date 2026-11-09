"""Engineering-only fixtures; never consume registered audit-world seeds."""
import math
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from research import readout_synthetic_world as w


class SyntheticWorldTests(unittest.TestCase):
    def test_world_support_pairing_and_reproducibility(self):
        a = w.make_world(0, 0., w.ENGINEERING_SEED)
        b = w.make_world(0, .15, w.ENGINEERING_SEED)
        repeat = w.make_world(0, .15, w.ENGINEERING_SEED)
        self.assertEqual(b['snapshot'], repeat['snapshot'])
        self.assertEqual(len(a['snapshot']['monthly']), 97)
        self.assertEqual(a['snapshot']['monthly'][0]['date'], '2014-12-31')
        for name in a['features']:
            np.testing.assert_array_equal(a['features'][name], b['features'][name])
        self.assertEqual(a['log_prices'][0], 0.)
        self.assertFalse(np.array_equal(a['log_prices'], b['log_prices']))

    def test_filter_against_joint_gaussian_conditioning(self):
        world = w.make_world(1, .15, w.ENGINEERING_SEED)
        # Three-month fixture includes truncated initial January observation.
        world['snapshot']['daily'] = world['snapshot']['daily'][:91]
        world['snapshot']['monthly'] = [{'date': '2012-03-31'}]
        prior = w.price_posteriors(world)['2012-03-31']
        dates = pd.DatetimeIndex([r['date'] for r in world['snapshot']['daily']])
        logs = np.log([r['price'] for r in world['snapshot']['daily']])
        n = np.array([30, 29, 31])
        loading = .15 * n / np.array([31, 29, 31])
        observed = []
        for month in (1, 2, 3):
            indexes = np.flatnonzero((dates.month == month) & (np.arange(len(dates)) > 0))
            observed.append(np.sum(logs[indexes] - logs[indexes - 1]))
        observed = np.array(observed) - n*w.MU/365
        covariance = w.PHI ** np.abs(np.arange(3)[:, None] - np.arange(3))
        yy = covariance * loading[:, None] * loading + np.diag(w.SIGMA**2*n/365)
        zy = w.PHI ** np.array([3, 2, 1]) * loading
        expected = (zy @ np.linalg.solve(yy, observed), 1 - zy @ np.linalg.solve(yy, zy))
        np.testing.assert_allclose(prior, expected, atol=1e-14)
        posterior = w.conditional_posterior(prior, 'noisy', .4)
        np.testing.assert_allclose(posterior, ((prior[0]+prior[1]*.4)/(1+prior[1]), prior[1]/(1+prior[1])))

    def test_terminal_moments_independent_daily_covariance(self):
        query, horizon, beta, posterior = '2019-12-31', 2, .15, (.3, .4)
        # Independent endpoint construction: Feb29 is retained, Jan1 excluded.
        dates = pd.date_range('2020-01-02', '2020-03-01')
        age = np.array(dates.month) - 1
        means = w.PHI**age * posterior[0]
        covariance = (w.PHI**np.abs(age[:, None] - age)
                      + (posterior[1]-1)*w.PHI**(age[:, None]+age))
        load = beta/np.array(dates.days_in_month)
        expected = (len(dates)*w.MU/365 + load @ means,
                    len(dates)*w.SIGMA**2/365 + load @ covariance @ load)
        np.testing.assert_allclose(w.terminal_moments(query, horizon, beta, posterior), expected, atol=1e-14)
        # Negative witness: reintroducing the excluded first increment must fail.
        original = w._future_calendar
        def broken(q, h):
            d, i = original(q, h)
            return d.insert(0, pd.Timestamp(q)+pd.Timedelta(days=1)), np.r_[0, i]
        with patch.object(w, '_future_calendar', broken):
            with self.assertRaises(AssertionError):
                np.testing.assert_allclose(w.terminal_moments(query, horizon, beta, posterior), expected, atol=1e-14)

    def test_future_simulation_moments_and_path_losses(self):
        args = ('2019-12-31', 2, .15, (.3, .4))
        draws = w.simulate_outcomes(*args, world_id=2, bank=0, root_seed=w.ENGINEERING_SEED, paths=10000)
        mean, variance = w.terminal_moments(*args)
        self.assertLess(abs(draws[:, 0].mean()-mean), 5*math.sqrt(variance/len(draws)))
        self.assertLess(abs(draws[:, 0].var()-variance), .06*variance)
        self.assertTrue((draws[:, 1:] >= 0).all())
        self.assertTrue((draws[:, 2] >= draws[:, 1]).all())
        # At beta zero, posterior changes have exactly no effect on any path.
        left = w.simulate_outcomes('2019-12-31', 1, 0., (0., 1.), 2, 0, w.ENGINEERING_SEED, 8)
        right = w.simulate_outcomes('2019-12-31', 1, 0., (99., 0.), 2, 0, w.ENGINEERING_SEED, 8)
        np.testing.assert_array_equal(left, right)

    def test_future_suffix_does_not_change_past_filter(self):
        world = w.make_world(3, .15, w.ENGINEERING_SEED)
        before = w.price_posteriors(world)
        for row in world['snapshot']['daily']:
            if row['date'] > '2019-12-31':
                row['price'] *= 2
        after = w.price_posteriors(world)
        for query in before:
            if query <= '2019-12-31':
                self.assertEqual(before[query], after[query])

    def test_gaussian_crps(self):
        self.assertAlmostEqual(w.gaussian_crps(0., 1., 0.), (math.sqrt(2)-1)/math.sqrt(math.pi))
        self.assertEqual(w.gaussian_crps(2., 0., 5.), 3.)


if __name__ == '__main__':
    unittest.main()
