import unittest

import numpy as np

from research.panel_score_contract import (
    normalize_gain, promotion_decision, score_selection, select_global,
)


class PanelScoreContractTests(unittest.TestCase):
    def test_global_choice_is_not_a_collection_of_world_winners(self):
        reference = np.full((2, 1, 2), 10.)
        candidate = np.array([[[[0., 0.], [4., 4.]]], [[[9., 9.], [4., 4.]]]])
        result = select_global(reference, candidate)
        # World zero prefers candidate zero; the single pooled winner is one.
        self.assertEqual(result["selected_cell"], 0)
        self.assertEqual(result["selected_candidate"], 1)
        self.assertEqual(result["reference_mean"], 10.)
        self.assertEqual(result["candidate_mean"], 4.)
        np.testing.assert_array_equal(score_selection(reference, candidate, 0, 1), [6., 6.])
        np.testing.assert_array_equal(score_selection(reference, candidate, 0, 0), [10., 1.])

    def test_aggregate_raw_losses_before_normalization(self):
        reference = np.array([[[1., 1.]], [[100., 100.]]])
        candidate = np.array([[[[0., 0.]]], [[[90., 90.]]]])
        result = select_global(reference, candidate)
        expected = 100 * (50.5 - 45) / (50.5 + 45)
        self.assertAlmostEqual(result["gain"], expected)
        self.assertNotAlmostEqual(result["gain"], float(normalize_gain([1, 100], [0, 90]).mean()))
        # Repeating origins within every world must not change their weighting.
        repeated = select_global(np.repeat(reference, 3, axis=-1), np.repeat(candidate, 3, axis=-1))
        self.assertAlmostEqual(repeated["gain"], result["gain"])

    def test_normalized_ranking_matches_classic_skill_and_first_ties(self):
        reference = np.array([1., 3., 10.])[:, None]
        candidate = np.array([[.5, 2.], [2., 7.], [9., 11.]])
        classic = 100 * (1 - candidate / reference)
        normalized = normalize_gain(reference, candidate)
        np.testing.assert_array_equal(np.argsort(classic.ravel()), np.argsort(normalized.ravel()))
        result = select_global(np.ones((2, 2, 3)), np.ones((2, 2, 4, 3)))
        self.assertEqual((result["selected_cell"], result["selected_candidate"], result["selected_index"]), (0, 0, 0))
        self.assertEqual(result["gain_matrix"].shape, (2, 4))

    def test_zero_loss_reference_and_large_finite_losses(self):
        np.testing.assert_array_equal(normalize_gain([0, 0, 3], [0, 4, 0]), [0, -100, 100])
        self.assertEqual(float(normalize_gain(1e308, 1e308)), 0.)
        self.assertAlmostEqual(float(normalize_gain(1e308, 5e307)), 100 / 3)
        result = select_global(np.zeros((2, 1, 3)), np.ones((2, 1, 1, 3)))
        self.assertEqual(result["gain"], -100.)

    def test_bad_shapes_missing_values_and_indices_fail_closed(self):
        reference = np.ones((2, 1, 3))
        candidate = np.ones((2, 1, 2, 3))
        for invalid in (np.ones((1, 1, 2, 3)), np.ones((2, 1, 2, 2)),
                        np.ones((2, 1, 0, 3)), np.ones((2, 1, 3)),
                        np.full(candidate.shape, np.nan), np.full(candidate.shape, -1),
                        np.full(candidate.shape, np.inf)):
            with self.subTest(shape=invalid.shape):
                with self.assertRaises(ValueError):
                    select_global(reference, invalid)
        with self.assertRaises(ValueError):
            normalize_gain(np.ones(2), np.ones(3))
        for cell, index in ((-1, 0), (1, 0), (0, 2), (True, 0)):
            with self.assertRaises(ValueError):
                score_selection(reference, candidate, cell, index)

    def test_synthetic_declaration_requires_rejection_and_positive_raw_gain(self):
        for pvalue, reference, candidate, expected in (
            (1., 1., .5, False), (1., 0., 0., False),
            (.01, 1., 2., False), (.01, 1., 1., False),
            (.01, 1., .5, True), (.05, 1., .5, True),
            (.05001, 1., .5, False),
        ):
            result = promotion_decision(pvalue, reference, candidate)
            self.assertEqual(result["promote"], expected)
            self.assertEqual(result["crt_reject"], pvalue <= .05)
            self.assertEqual(result["positive_gain"], reference > candidate)
            self.assertEqual(result["raw_gain"], reference - candidate)

    def test_invalid_declaration_arguments_are_rejected(self):
        for pvalue, reference, candidate, alpha in (
            (np.nan, 1., .5, .05), (-.1, 1., .5, .05), (1.1, 1., .5, .05),
            (.01, 1., .5, 0.), (.01, 1., .5, 1.), (.01, 1., .5, np.inf),
            (.01, -1., .5, .05), (.01, 1., np.nan, .05),
            (.01, [1.], [.5], .05),
        ):
            with self.assertRaises(ValueError):
                promotion_decision(pvalue, reference, candidate, alpha)


if __name__ == "__main__":
    unittest.main()
