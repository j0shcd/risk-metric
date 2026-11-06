from dataclasses import replace
import unittest

import numpy as np

from research.batched_scenarios import null_scores, worlds
from research.conditional_search import redraw_scores
from research.search_qualification import NULLS, POSITIVES, SearchConfig, world


class BatchedScenariosTests(unittest.TestCase):
    def test_every_family_matches_scalar_rng_and_arithmetic_exactly(self):
        for seed, size, candidates in ((371, 72, 4), (9081, 125, 7)):
            config = SearchConfig(seed=seed, steps=size, candidates=candidates)
            indices = [0, 3, 17]
            for kind in (*NULLS, *POSITIVES):
                with self.subTest(seed=seed, kind=kind):
                    actual = worlds(config, 402, indices, kind)
                    expected = [world(config, 402, index, kind) for index in indices]
                    for component in range(3):
                        np.testing.assert_array_equal(actual[component], np.stack([row[component] for row in expected]))

    def test_batch_membership_and_order_never_change_a_world(self):
        config = SearchConfig(seed=81, steps=40, candidates=3)
        for kind in (*NULLS, *POSITIVES):
            panel = worlds(config, 42, [1, 7, 9], kind)
            reordered = worlds(config, 42, [9, 1], kind)
            alone = worlds(config, 42, [7], kind)
            for original, changed, single in zip(panel, reordered, alone):
                np.testing.assert_array_equal(changed, original[[2, 0]])
                np.testing.assert_array_equal(single[0], original[1])

    def test_monthly_context_conventions_and_short_paths(self):
        config = SearchConfig(seed=981, steps=31, candidates=2)
        price, context, _ = worlds(config, 20, [5], "gaussian_p95")
        np.testing.assert_array_equal(context[:, :12], 0)
        self.assertEqual(context[0, 12, 0], price[0, 12] - price[0, 0])
        self.assertAlmostEqual(context[0, 12, 1], np.std(np.diff(price[0, :13]), ddof=1))
        for size in (1, 2, 12):
            small = replace(config, steps=size)
            for kind in (*NULLS, *POSITIVES):
                actual = worlds(small, 20, [5], kind)
                expected = world(small, 20, 5, kind)
                for batched, scalar in zip(actual, expected):
                    np.testing.assert_array_equal(batched[0], scalar)

    def test_null_scores_match_scalar_calls_and_batch_membership(self):
        for seed, candidates in ((43, 3), (901, 24)):
            indices = [0, 4, 17]
            contexts = np.random.default_rng(6).normal(size=(3, 57, 2))
            actual = null_scores(seed, 808, indices, contexts, candidates)
            expected = []
            for index, context in zip(indices, contexts):
                rng = np.random.default_rng(np.random.SeedSequence([seed, 808, index]))
                expected.append(redraw_scores(rng, context, 1, candidates, .5)[0])
            np.testing.assert_array_equal(actual, np.stack(expected))
            reordered = null_scores(seed, 808, [17, 0], contexts[[2, 0]], candidates)
            np.testing.assert_array_equal(reordered, actual[[2, 0]])
            np.testing.assert_array_equal(null_scores(seed, 808, [4], contexts[[1]], candidates)[0], actual[1])

    def test_invalid_indices_families_and_context_shapes_fail(self):
        config = SearchConfig(steps=20)
        for indices in ([], [1, 1], [-1], [True], [1.5], (1, 2)):
            with self.assertRaises(ValueError):
                worlds(config, 0, indices, "gaussian_p50")
        for domain in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                worlds(config, domain, [0], "gaussian_p50")
        with self.assertRaises(ValueError):
            worlds(config, 0, [0], "undeclared")
        for context in (np.zeros((2, 20, 2)), np.zeros((1, 20, 3)),
                        np.zeros((1, 0, 2)), np.full((1, 20, 2), np.nan)):
            with self.assertRaises(ValueError):
                null_scores(1, 0, [0], context)
        with self.assertRaises(ValueError):
            null_scores(1, 0, [0], np.zeros((1, 20, 2)), candidates=0)


if __name__ == "__main__":
    unittest.main()
