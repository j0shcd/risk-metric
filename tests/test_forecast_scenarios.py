from dataclasses import replace
import math
import unittest

import numpy as np

from research.forecast_oracles import normal_crps, state_bin_losses, tail_oracle_losses
from research.forecast_pilot import PilotConfig, run_campaign
from research.forecast_readout import crps_empirical
from research.forecast_scenarios import control_world, forward_log_returns, overlap_null, partition_world


class ForecastScenarioTests(unittest.TestCase):
    def test_ticket_contains_only_returns_after_execution(self):
        def outcome(increments):
            prices = np.r_[0., np.cumsum(increments)]
            return float(forward_log_returns(prices, np.array([0]), 2)[0][0])
        self.assertEqual(outcome([0, 0, 0, 0]), 0)
        self.assertEqual(outcome([10, 0, 0, 0]), 0)  # Move paid in the entry price.
        self.assertEqual(outcome([0, 10, 0, 0]), 10)
        self.assertEqual(outcome([0, 0, 10, 0]), 10)
        self.assertEqual(outcome([0, 0, 0, 10]), 0)

    def test_continuous_path_outcomes_and_phase_maturity_are_preserved(self):
        config = PilotConfig()
        world = overlap_null(20261106, 0)
        partition = partition_world(world, config)
        self.assertEqual(partition.status, "eligible")
        for phase, indices in zip(partition.phases, partition.indices):
            np.testing.assert_array_equal(phase.outcomes, world.log_price[world.outcome_end[indices]] - world.log_price[world.execution[indices]])
            np.testing.assert_array_equal(phase.context, world.context[indices])
        for previous, following in zip(partition.phases, partition.phases[1:]):
            self.assertLess(previous.label_available_step.max(), following.decision_step.min())
        self.assertLessEqual(partition.phases[-1].label_available_step.max(), world.asof)
        self.assertTrue(np.any(np.diff(world.decision) < 48))  # Dependence retained within phases.

    def test_btc_sized_path_is_insufficient_even_with_small_phase_minimums(self):
        config = replace(PilotConfig(), fit_rows=24, phase_rows=24)
        result = partition_world(overlap_null(20261106, 0, steps=140), config)
        self.assertEqual(result.status, "insufficient_evidence")
        self.assertEqual(result.phases, ())
        self.assertIn("calibration", result.reason)

    def test_publication_boundary_precedes_any_scoring(self):
        config = replace(PilotConfig(), candidates=1)
        leading = control_world(12, 0, "leading")
        self.assertEqual(partition_world(leading, config).status, "eligible")
        earlier = replace(leading, observation=leading.observation - 1, publication=leading.publication - 1)
        self.assertEqual(partition_world(earlier, config).status, "eligible")
        late = replace(leading, publication=leading.publication + 1)
        self.assertEqual(partition_world(late, config).status, "ineligible")
        revised = control_world(12, 0, "revised")
        self.assertEqual(partition_world(revised, config).status, "ineligible")
        with self.assertRaises(ValueError):
            partition_world(replace(leading, observation=leading.publication + 1), config)

    def test_timing_controls_share_outcomes_and_leading_signal_is_post_entry(self):
        config = replace(PilotConfig(), candidates=1)
        leading = control_world(20261106, 0, "leading")
        lagging = control_world(20261106, 0, "lagging")
        np.testing.assert_array_equal(leading.outcomes, lagging.outcomes)
        np.testing.assert_array_equal(leading.log_price, lagging.log_price)
        np.testing.assert_allclose(leading.outcomes, leading.log_price[leading.outcome_end] - leading.log_price[leading.execution])
        first = run_campaign(partition_world(leading, config).phases, config)[0]
        second = run_campaign(partition_world(lagging, config).phases, config)[0]
        self.assertGreater(first["audit_skill"], second["audit_skill"] + 10)

    def test_tail_oracle_population_loss_has_known_exact_gap(self):
        states = np.array([0., 0., 1., 1.])
        outcomes = np.array([-1., 1., -3., 3.])
        pooled, conditional = tail_oracle_losses(states, outcomes)
        self.assertEqual(float(pooled.mean()), 1.25)
        self.assertEqual(float(conditional.mean()), 1.0)
        self.assertEqual(float(outcomes[states == 0].mean()), 0)
        self.assertEqual(float(outcomes[states == 1].mean()), 0)
        self.assertAlmostEqual(100 * (1 - conditional.mean() / pooled.mean()), 20)

    def test_state_bins_retain_sparse_rows_and_use_calibration_only(self):
        states = np.r_[np.zeros(20), np.ones(2)]
        outcomes = np.r_[np.tile([-1., 1.], 10), [-3., 3.]]
        audit_states = np.array([0., 1., 1.])
        audit = np.array([-1., -3., 3.])
        losses, fallback = state_bin_losses(states, outcomes, audit_states, audit)
        self.assertEqual(fallback, 2)
        np.testing.assert_allclose(losses[1:], crps_empirical(outcomes, audit[1:]))
        with self.assertRaises(ValueError):
            state_bin_losses(states, outcomes, np.array([2.]), np.array([0.]))

    def test_gaussian_oracle_closed_form_and_redundant_context(self):
        self.assertAlmostEqual(float(normal_crps(np.array([0.]), np.array([0.]), 1)[0]), (math.sqrt(2) - 1) / math.sqrt(math.pi))
        values = normal_crps(np.array([0., 0.]), np.array([-2., 2.]), .5)
        self.assertEqual(values[0], values[1])
        world = control_world(9, 0, "redundant")
        np.testing.assert_array_equal(world.indicators[:, 0], world.context**2)
        context_mean = -2 * world.context**2
        indicator_mean = -2 * world.indicators[:, 0]
        np.testing.assert_array_equal(normal_crps(context_mean, world.outcomes, .5), normal_crps(indicator_mean, world.outcomes, .5))

    def test_gaussian_oracle_matches_cdf_integral(self):
        # Independent numerical definition: integral (F(x)-1{x>=y})² dx.
        grid = np.linspace(-5., 5., 30001)
        cdf = np.array([.5 * (1 + math.erf(x / (.5 * math.sqrt(2)))) for x in grid])
        integral = np.trapezoid((cdf - (grid >= .7))**2, grid)
        self.assertAlmostEqual(float(normal_crps(np.array([0.]), np.array([.7]), .5)[0]), integral, delta=.0005)

    def test_audit_batch_cannot_refit_state_bin_forecasts(self):
        calibration_states = np.array([0., 0., 1., 1.])
        calibration = np.array([-1., 1., -3., 3.])
        audit_states = np.zeros(3)
        first, _ = state_bin_losses(calibration_states, calibration, audit_states, np.array([-1., 1., 1.]), minimum_per_state=1)
        changed, _ = state_bin_losses(calibration_states, calibration, audit_states, np.array([-1., 100., 100.]), minimum_per_state=1)
        self.assertEqual(first[0], changed[0])


if __name__ == "__main__":
    unittest.main()
