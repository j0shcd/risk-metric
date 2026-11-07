import unittest

import numpy as np

from research.conditional_score_law import draw_future_scores, posterior_shared_state


def direct_condition(history, sigma, candidate, future_steps):
    """Joint Gaussian conditioning, independent of the filtering recursion."""
    times, candidates = history.shape
    observed_t = np.repeat(np.arange(times), candidates)
    observed_j = np.tile(np.arange(candidates), times)
    lag = np.abs(observed_t[:, None] - observed_t[None, :])
    cov = .95**lag + (observed_j[:, None] == observed_j[None, :]) * sigma[observed_j[:, None]]**2 * .5**lag
    future_t = times + np.arange(future_steps)
    cross_lag = np.abs(future_t[:, None] - observed_t[None, :])
    cross = .95**cross_lag + (observed_j[None, :] == candidate) * sigma[candidate]**2 * .5**cross_lag
    future_lag = np.abs(future_t[:, None] - future_t[None, :])
    future_cov = .95**future_lag + sigma[candidate]**2 * .5**future_lag
    solve = np.linalg.solve(cov, cross.T)
    mean = cross @ np.linalg.solve(cov, history.ravel())
    return mean, future_cov - cross @ solve, cov


class ConditionalScoreLawTests(unittest.TestCase):
    def setUp(self):
        self.sigma = np.array([.2, .9, 1.8])
        self.history = np.random.default_rng(17).normal(size=(2, 5, 3))

    def test_shared_posterior_matches_direct_joint_conditioning(self):
        means, variance = posterior_shared_state(self.history, self.sigma)
        _, _, covariance = direct_condition(self.history[0], self.sigma, 1, 3)
        cov_z_s = np.repeat(-.95**(4 - np.arange(5)), 3)
        expected_variance = 1 - cov_z_s @ np.linalg.solve(covariance, cov_z_s)
        for i, history in enumerate(self.history):
            self.assertAlmostEqual(means[i], cov_z_s @ np.linalg.solve(covariance, history.ravel()), places=11)
        self.assertAlmostEqual(variance, expected_variance, places=11)

    def test_future_mean_and_covariance_match_direct_conditioning(self):
        draws = draw_future_scores(self.history, self.sigma, 1, 3, 80000, np.random.default_rng(33))
        self.assertEqual(draws.shape, (80000, 2, 3))
        for i in range(2):
            expected_mean, expected_covariance, _ = direct_condition(self.history[i], self.sigma, 1, 3)
            np.testing.assert_allclose(draws[:, i].mean(axis=0), expected_mean, atol=.018)
            np.testing.assert_allclose(np.cov(draws[:, i].T), expected_covariance, atol=.025)
        self.assertLess(abs(np.cov(draws[:, 0, 0], draws[:, 1, 0])[0, 1]), .02)

    def test_all_prefix_candidates_matter_and_seed_is_reproducible(self):
        first = posterior_shared_state(self.history, self.sigma)[0]
        altered = self.history.copy()
        altered[:, 2, 0] += 2
        self.assertGreater(np.max(abs(first - posterior_shared_state(altered, self.sigma)[0])), .001)
        a = draw_future_scores(self.history, self.sigma, 2, 4, 5, np.random.default_rng(91))
        b = draw_future_scores(self.history, self.sigma, 2, 4, 5, np.random.default_rng(91))
        np.testing.assert_array_equal(a, b)
        # Typical registered shape works without requiring exactly 24 candidates.
        history = np.zeros((1, 2, 24))
        self.assertEqual(draw_future_scores(history, np.linspace(.1, 2, 24), 23, 2, 3, np.random.default_rng(4)).shape, (3, 1, 2))

    def test_rejects_invalid_inputs(self):
        for history, sigma in [(self.history[0], self.sigma), (self.history, [1., 0., 2.]),
                               (self.history, [1., 2.]), (np.full((1, 2, 3), np.nan), self.sigma),
                               (np.zeros((0, 1, 3)), self.sigma)]:
            with self.assertRaises(ValueError):
                posterior_shared_state(history, sigma)
        for candidate, steps, draws, rng in [(-1, 1, 1, np.random.default_rng()), (3, 1, 1, np.random.default_rng()),
                                              (0, 0, 1, np.random.default_rng()), (0, 1, 0, np.random.default_rng()),
                                              (0, 1, 1, None)]:
            with self.assertRaises(ValueError):
                draw_future_scores(self.history, self.sigma, candidate, steps, draws, rng)


if __name__ == "__main__":
    unittest.main()
