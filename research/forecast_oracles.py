"""Analytical controls for known synthetic distributions, not fitted forecasts."""

from __future__ import annotations

import math

import numpy as np

from .forecast_readout import crps_empirical, finite_vector


def normal_crps(means: np.ndarray, outcomes: np.ndarray, sigma: float) -> np.ndarray:
    means = finite_vector(means, "normal means")
    outcomes = finite_vector(outcomes, "normal outcomes")
    if len(means) != len(outcomes) or not np.isfinite(sigma) or sigma <= 0:
        raise ValueError("normal oracle needs matching support and positive sigma")
    z = (outcomes - means) / sigma
    erf = np.fromiter((math.erf(float(x) / math.sqrt(2)) for x in z), float, count=len(z))
    return sigma * (z * erf + math.sqrt(2 / math.pi) * np.exp(-z*z/2) - 1 / math.sqrt(math.pi))


def tail_oracle_losses(states: np.ndarray, outcomes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    states = finite_vector(states, "tail states")
    outcomes = finite_vector(outcomes, "tail outcomes")
    if len(states) != len(outcomes) or not np.isin(states, [0, 1]).all():
        raise ValueError("tail oracle requires common binary-state support")
    pooled = crps_empirical(np.array([-3., -1., 1., 3.]), outcomes)
    conditional = np.empty(len(states))
    for state in (0, 1):
        selected = states == state
        amplitude = 1 + 2 * state
        conditional[selected] = crps_empirical(np.array([-amplitude, amplitude]), outcomes[selected])
    return pooled, conditional


def state_bin_losses(calibration_states: np.ndarray, calibration_outcomes: np.ndarray,
                     audit_states: np.ndarray, audit_outcomes: np.ndarray,
                     minimum_per_state: int = 12) -> tuple[np.ndarray, int]:
    """Registered {0,1} bins; sparse bins use pooled calibration, never drop rows."""
    calibration_states = finite_vector(calibration_states, "calibration states")
    calibration_outcomes = finite_vector(calibration_outcomes, "calibration outcomes")
    audit_states = finite_vector(audit_states, "audit states")
    audit_outcomes = finite_vector(audit_outcomes, "audit outcomes")
    if (len(calibration_states) != len(calibration_outcomes) or len(audit_states) != len(audit_outcomes)
            or not np.isin(calibration_states, [0, 1]).all() or not np.isin(audit_states, [0, 1]).all()
            or type(minimum_per_state) is not int or minimum_per_state < 1):
        raise ValueError("state-bin forecasts require matching binary support and a positive minimum")
    losses = np.empty(len(audit_states))
    fallback = 0
    for state in (0, 1):
        selected = audit_states == state
        if not selected.any():
            continue
        samples = calibration_outcomes[calibration_states == state]
        if len(samples) < minimum_per_state:
            samples = calibration_outcomes
            fallback += int(selected.sum())
        losses[selected] = crps_empirical(samples, audit_outcomes[selected])
    return losses, fallback
