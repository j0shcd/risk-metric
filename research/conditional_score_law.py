"""Exact synthetic score continuation given the complete observed score prefix.

This law is specific to the declared Gaussian AR generator. It does not supply
or estimate a Bitcoin score law. Inputs must have the known context shift removed.
"""

from __future__ import annotations

import numpy as np

RHO = .95
PSI = .5


def _validate(history, sigma):
    history = np.asarray(history, dtype=float)
    sigma = np.asarray(sigma, dtype=float)
    if (history.ndim != 3 or min(history.shape) < 1 or sigma.ndim != 1
            or sigma.shape != (history.shape[2],) or not np.isfinite(history).all()
            or not np.isfinite(sigma).all() or np.any(sigma <= 0)):
        raise ValueError("require finite [world,time,candidate] history and positive matching sigma")
    # Normalizing first avoids overflowing inverse variances for small sigmas.
    relative = sigma.min() / sigma
    weights = relative**2
    weights /= weights.sum()
    variance = (sigma.min() / np.sqrt(np.sum(relative**2)))**2
    if not np.isfinite(variance) or variance <= 0:
        raise ValueError("sigma values must yield a representable positive observation variance")
    return history, sigma, weights, variance


def posterior_shared_state(history, sigma):
    """Return E[Z_cut | all score prefixes] per world and common posterior variance.

    Each stationary residual score is S_j,t = -Z_t + sigma_j E_j,t,
    with independent shared AR(.95) and idiosyncratic AR(.5) processes.
    """
    history, _, weights, observation_variance = _validate(history, sigma)
    mean = -(history[:, 0, :] @ weights) / (1 + observation_variance)
    variance = observation_variance / (1 + observation_variance)
    q = 1 - RHO**2
    innovation_variance = (1 - PSI**2) * observation_variance
    for t in range(1, history.shape[1]):
        a = (history[:, t, :] - PSI * history[:, t - 1, :]) @ weights
        predicted_variance = RHO**2 * variance + q
        cross_covariance = -predicted_variance + PSI * RHO * variance
        residual_variance = (predicted_variance + PSI**2 * variance
                             - 2 * PSI * RHO * variance + innovation_variance)
        mean = RHO * mean + cross_covariance / residual_variance * (a - (PSI - RHO) * mean)
        variance = predicted_variance - cross_covariance**2 / residual_variance
    return mean, float(max(0., variance))


def draw_future_scores(history, sigma, candidate, steps, draws, rng):
    """Draw [draw,world,future_time] selected-score residual continuations.

    Every draw and world receives independent innovations. The fixed, observed
    prefix includes *all* candidate scores; the caller may add the known future
    context shift afterward. No future price or outcome enters this function.
    """
    history, sigma, _, _ = _validate(history, sigma)
    if (type(candidate) is not int or not 0 <= candidate < len(sigma)
            or type(steps) is not int or steps < 1
            or type(draws) is not int or draws < 1
            or not isinstance(rng, np.random.Generator)):
        raise ValueError("require a valid candidate, positive steps/draws and numpy Generator")
    mean, variance = posterior_shared_state(history, sigma)
    z = mean[None, :] + np.sqrt(variance) * rng.normal(size=(draws, len(history)))
    e = (history[None, :, -1, candidate] + z) / sigma[candidate]
    result = np.empty((draws, len(history), steps))
    for t in range(steps):
        z = RHO*z + np.sqrt(1-RHO**2)*rng.normal(size=z.shape)
        e = PSI*e + np.sqrt(1-PSI**2)*rng.normal(size=e.shape)
        result[:, :, t] = -z + sigma[candidate]*e
    return result
