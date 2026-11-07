from dataclasses import replace
import unittest

import numpy as np

from research.location_scale_readout import calibration_residuals, empirical_loss, fit_mean_scale
from research.location_scale_search import ContinuousConfig, feature_phases, phases, prepare, search_statistics
from research.search_qualification import SearchConfig, world


class LocationScaleSearchTests(unittest.TestCase):
    def test_fixed_phases_clear_all_horizons_and_short_market_history_is_infeasible(self):
        config = ContinuousConfig()
        fit, cal, dev, audit = phases(config)
        self.assertEqual([len(i) for i in (fit, cal, dev, audit)], [192, 96, 96, 96])
        self.assertEqual((fit[-1], cal[0], cal[-1], dev[0], dev[-1], audit[0], audit[-1]), (203, 254, 349, 400, 495, 546, 641))
        for previous, following in zip((fit, cal, dev), (cal, dev, audit)):
            self.assertLess(previous[-1]+max(config.horizons)+2, following[0])
        self.assertLess(audit[-1]+max(config.horizons)+2, config.steps)
        with self.assertRaisesRegex(ValueError, "insufficient history"): phases(replace(config, steps=140))

    def test_exact_context_duplicate_cannot_change_regularization_or_forecast(self):
        rng = np.random.default_rng(5)
        context = rng.normal(size=(720, 2))
        scores = (3+7*context[:, 0]-2*context[:, 1])[None, :, None]
        context[546:] += 100  # Arbitrary audit shift cannot activate an absent fit feature.
        scores[:, 546:] += 1000
        ref, candidate = feature_phases(context, scores, phases(ContinuousConfig()))
        np.testing.assert_array_equal(candidate[0][..., -1], 0)
        y, cal_y = rng.normal(size=192), rng.normal(size=96)
        a, b = fit_mean_scale(ref[0], y), fit_mean_scale(candidate[0], y)
        ar, br = calibration_residuals(a, ref[1], cal_y), calibration_residuals(b, candidate[1], cal_y)
        am, ass = a.predict(ref[3]); bm, bs = b.predict(candidate[3])
        np.testing.assert_allclose(am, bm, atol=1e-12)
        np.testing.assert_allclose(ass, bs, atol=1e-12)
        np.testing.assert_allclose(ar, br, atol=1e-12)

    def test_feature_transform_is_fit_only_and_indicator_affine_invariant(self):
        rng = np.random.default_rng(6)
        context, scores = rng.normal(size=(720, 2)), rng.normal(size=(2, 720, 3))
        selected = phases(ContinuousConfig())
        _, before = feature_phases(context, scores, selected)
        _, scaled = feature_phases(context, 11+7*scores, selected)
        for a, b in zip(before, scaled): np.testing.assert_allclose(a, b, atol=1e-12)
        changed = scores.copy(); changed[:, 256:] += 100
        _, after = feature_phases(context, changed, selected)
        np.testing.assert_array_equal(before[0], after[0])
        np.testing.assert_array_equal(before[1][:, :, :2], after[1][:, :, :2])
        changed_context = context.copy(); changed_context[256:] += 100
        _, context_after = feature_phases(changed_context, scores, selected)
        np.testing.assert_array_equal(before[0], context_after[0])
        np.testing.assert_array_equal(before[1][:, :, :2], context_after[1][:, :, :2])

    def test_batch_draws_equal_single_draw_search_and_audit_cannot_select(self):
        config = replace(ContinuousConfig(), candidates=3)
        price, context, scores = world(SearchConfig(candidates=3), 1, 2, "leading_location")
        draws = np.stack([scores, np.roll(scores, 120, axis=0)])
        prepared = prepare(config, price, context)
        values, selected, attempts = search_statistics(prepared, draws)
        for i in range(2):
            scalar, index, dev = search_statistics(prepared, draws[i:i+1])
            self.assertAlmostEqual(values[i], scalar[0], places=10)
            self.assertEqual(selected[i], index[0])
            np.testing.assert_allclose(attempts[i], dev[0], atol=1e-10)
        future = price.copy(); future[546:] += np.arange(len(price)-546)*100
        after, new_selected, new_dev = search_statistics(prepare(config, future, context), draws)
        np.testing.assert_array_equal(selected, new_selected)
        np.testing.assert_array_equal(attempts, new_dev)
        self.assertFalse(np.array_equal(values, after))
        with self.assertRaisesRegex(ValueError, "identical finite score path"):
            search_statistics(prepared, draws[:, :-1])


if __name__ == "__main__":
    unittest.main()
