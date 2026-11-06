from dataclasses import replace
import unittest
from unittest.mock import patch

import numpy as np

from research.conditional_search import prepare, rank_pvalue, redraw_scores, search_statistics
from research.search_qualification import SearchConfig, campaign, phase_indices, world


class ConditionalSearchTests(unittest.TestCase):
    def test_batched_search_repeats_the_entire_frozen_search(self):
        config = replace(SearchConfig(), candidates=4)
        price, context, _ = world(config, 2, 1, "leading_location")
        draws = redraw_scores(np.random.default_rng(6), context, 3, config.candidates)
        values, selected, attempts = search_statistics(prepare(config, price, context), draws)
        for i in range(len(draws)):
            with patch("research.search_qualification.world", return_value=(price, context, draws[i])):
                original = campaign(config, 0, 0, "leading_location")
            self.assertAlmostEqual(values[i], original["audit_skill"], places=11)
            flattened = ((list(config.horizons).index(original["selected_horizon"])*3
                          + original["selected_target"])*config.candidates+original["selected_candidate"])
            self.assertEqual(selected[i], flattened)
            np.testing.assert_allclose(attempts[i], [r["skill"] for r in original["development_attempts"]], atol=1e-11)

    def test_whole_path_draws_preserve_declared_covariance_and_context_shift(self):
        context = np.array([[3., 0], [1., 0], [-2., 0], [4., 0]])
        innovation = redraw_scores(np.random.default_rng(4), context, 10000, 3, 0.)
        shifted = redraw_scores(np.random.default_rng(4), context, 10000, 3, .5)
        np.testing.assert_allclose(shifted-innovation, np.broadcast_to(.5*context[None, :, 0, None], shifted.shape), atol=1e-15)
        empirical = np.cov(np.column_stack((innovation[:, 0, 0], innovation[:, 1, 0], innovation[:, 0, 1])), rowvar=False)
        self.assertAlmostEqual(empirical[0, 0], 1+.1**2, delta=.05)
        self.assertAlmostEqual(empirical[0, 1], .95+.1**2*.5, delta=.05)
        self.assertAlmostEqual(empirical[0, 2], 1., delta=.05)

    def test_ties_plus_one_and_exchangeable_rank_enumeration(self):
        self.assertEqual(rank_pvalue(0, np.zeros(99)), 1.)
        self.assertEqual(rank_pvalue(2, np.ones(99)), .01)
        self.assertEqual(rank_pvalue(1, np.r_[np.ones(4), np.zeros(95)]), .05)
        values = np.array([0, 0, 1, 3, 3, 5, 8, 9, 10, 11], float)
        pvalues = [rank_pvalue(value, np.delete(values, i)) for i, value in enumerate(values)]
        for alpha in (.1, .2, .3, .5):
            self.assertLessEqual(np.mean(np.array(pvalues) <= alpha), alpha)

    def test_audit_changes_cannot_change_selection_and_missing_paths_fail(self):
        config = replace(SearchConfig(), candidates=4)
        price, context, scores = world(config, 2, 1, "leading_location")
        prepared = prepare(config, price, context)
        values, selected, attempts = search_statistics(prepared, scores[None])
        latest_development_label = max(phase_indices(config, h)[2][-1]+h+2 for h in config.horizons)
        changed = price.copy()
        changed[latest_development_label+1:] += np.arange(len(changed)-latest_development_label-1)*100
        after, new_selected, new_attempts = search_statistics(prepare(config, changed, context), scores[None])
        np.testing.assert_array_equal(selected, new_selected)
        np.testing.assert_array_equal(attempts, new_attempts)
        self.assertNotEqual(values[0], after[0])
        with self.assertRaisesRegex(ValueError, "identical finite path"):
            search_statistics(prepared, scores[None, :-1])


if __name__ == "__main__":
    unittest.main()
