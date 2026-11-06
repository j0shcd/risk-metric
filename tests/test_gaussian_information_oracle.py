from dataclasses import replace
import math
import unittest

import numpy as np

from research.gaussian_information_oracle import GaussianLaw, normal_loss, state_posterior, terminal_law
from research.search_qualification import SearchConfig, world


class GaussianInformationOracleTests(unittest.TestCase):
    def test_filter_agrees_with_independent_batch_gaussian_conditioning(self):
        law = GaussianLaw()
        price, _, scores = world(SearchConfig(steps=40), 203, 11, "leading_location")
        returns = np.diff(np.r_[0., price])
        for include_score in (False, True):
            means, variances = state_posterior(price, law, scores[:, 0] if include_score else None)
            for t in (2, 5, 12):
                r = np.arange(2, t+1)
                s = np.arange(t+1) if include_score else np.empty(0, int)
                rr = law.return_loading**2*law.persistence**abs(r[:, None]-r)
                rr += np.eye(len(r))*law.return_noise**2
                rs = -law.return_loading*law.persistence**abs((r[:, None]-2)-s)
                ss = law.persistence**abs(s[:, None]-s)+law.score_noise**2*law.score_noise_persistence**abs(s[:, None]-s)
                covariance = np.block([[rr, rs], [rs.T, ss]])
                cross = np.r_[law.return_loading*law.persistence**(t-r+2), -law.persistence**(t-s)]
                observations = np.r_[returns[r], scores[s, 0]]
                expected_mean = cross @ np.linalg.solve(covariance, observations)
                expected_variance = 1-cross @ np.linalg.solve(covariance, cross)
                self.assertAlmostEqual(means[t], expected_mean, places=11)
                self.assertAlmostEqual(variances[t], expected_variance, places=11)

    def test_terminal_law_matches_independent_covariance_sum(self):
        law = GaussianLaw()
        for horizon in (1, 12, 24, 48):
            means, variances = terminal_law(np.array([.7]), np.array([.2]), horizon, law)
            k = np.arange(horizon)
            expected_mean = law.return_loading*np.sum(law.persistence**k)*.7
            state_covariance = law.persistence**abs(k[:, None]-k)-.8*law.persistence**(k[:, None]+k)
            expected_variance = horizon*law.return_noise**2+law.return_loading**2*state_covariance.sum()
            self.assertAlmostEqual(means[0], expected_mean, places=12)
            self.assertAlmostEqual(variances[0], expected_variance, places=12)

    def test_future_suffix_cannot_change_existing_posterior_or_forecast(self):
        price, _, scores = world(SearchConfig(steps=80), 203, 7, "leading_location")
        before = state_posterior(price, GaussianLaw(), scores[:, 0])
        price[21:] += 100
        scores[21:, 0] -= 100
        after = state_posterior(price, GaussianLaw(), scores[:, 0])
        for left, right in zip(before, after):
            np.testing.assert_array_equal(left[:21], right[:21])

    def test_perfect_score_reveals_state_and_noisy_score_approaches_price_only(self):
        price = np.zeros(80)
        _, reference = state_posterior(price, GaussianLaw())
        _, exact = state_posterior(price, replace(GaussianLaw(), score_noise=0), np.zeros(80))
        _, noisy = state_posterior(price, replace(GaussianLaw(), score_noise=1e8), np.zeros(80))
        np.testing.assert_allclose(exact, 0, atol=1e-15)
        np.testing.assert_allclose(noisy, reference, atol=1e-12)

    def test_normal_crps_agrees_with_cdf_integral(self):
        mean, variance, y = .7, 1.3, -.4
        grid = np.linspace(-12, 12, 100001)
        cdf = np.fromiter((.5*(1+math.erf((x-mean)/math.sqrt(2*variance))) for x in grid), float)
        # Integrate separately at the CDF's indicator discontinuity.
        left = np.r_[grid[grid < y], y]
        right = np.r_[y, grid[grid > y]]
        cdf_y = .5*(1+math.erf((y-mean)/math.sqrt(2*variance)))
        integral = np.trapezoid(np.r_[cdf[grid < y], cdf_y]**2, left)
        integral += np.trapezoid((1-np.r_[cdf_y, cdf[grid > y]])**2, right)
        actual = normal_loss(np.array([mean]), np.array([variance]), np.array([y]))[0]
        self.assertAlmostEqual(actual, integral, places=7)


if __name__ == "__main__":
    unittest.main()
