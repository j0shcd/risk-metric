"""Known-law, observed-data oracle for the frozen location simulation only.

The price process is r[t] = loading * state[t-2] + noise * epsilon[t]
for t>=2, with stationary AR(1) state. The score is -state[t] plus an
independent stationary AR(1) measurement error. Both laws/parameters are
known here; estimating them on market data would be a different procedure.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class GaussianLaw:
    persistence: float = .95
    return_loading: float = .08
    return_noise: float = .04
    score_noise: float = .1
    score_noise_persistence: float = .5

    def validate(self):
        values = (self.persistence, self.return_loading, self.return_noise,
                  self.score_noise, self.score_noise_persistence)
        if (not np.isfinite(values).all() or abs(self.persistence) >= 1
                or abs(self.score_noise_persistence) >= 1
                or self.return_noise <= 0 or self.score_noise < 0):
            raise ValueError("require a stationary finite Gaussian law and positive return noise")


def state_posterior(log_price: np.ndarray, law: GaussianLaw, scores: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Posterior state at each decision, given causal price and optional scores.

    State = [s_t, s_(t-1), s_(t-2), measurement_error_t]. No latent state is
    supplied. Prices include r_0 = log_price[0], which has no state loading
    in the frozen generator. Observation of the current close/score precedes
    forecasting; no forward price, score or mature outcome enters this filter.
    """
    law.validate()
    price = np.asarray(log_price, float)
    if price.ndim != 1 or not len(price) or not np.isfinite(price).all():
        raise ValueError("require a nonempty finite log-price vector")
    score = None if scores is None else np.asarray(scores, float)
    if score is not None and (score.shape != price.shape or not np.isfinite(score).all()):
        raise ValueError("scores must cover the identical finite decision history")
    phi, psi = law.persistence, law.score_noise_persistence
    transition = np.array([[phi, 0, 0, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, psi]], float)
    innovation = np.diag([1-phi**2, 0, 0, 1-psi**2])
    covariance = np.zeros((4, 4))
    covariance[:3, :3] = phi ** np.abs(np.arange(3)[:, None]-np.arange(3))
    covariance[3, 3] = 1
    mean = np.zeros(4)
    means, variances = np.empty(len(price)), np.empty(len(price))
    increments = np.diff(np.r_[0., price])

    def observe(observation, row, variance):
        nonlocal mean, covariance
        cross = covariance @ row
        total = float(row @ cross + variance)
        if total <= 0 or not np.isfinite(total):
            raise ValueError("singular observation law")
        gain = cross/total
        mean = mean + gain*(observation-row @ mean)
        # Joseph update preserves covariance symmetry/positive semidefiniteness.
        residual = np.eye(4)-np.outer(gain, row)
        covariance = residual @ covariance @ residual.T + variance*np.outer(gain, gain)
        covariance = (covariance+covariance.T)/2

    for t in range(len(price)):
        if t:
            mean = transition @ mean
            covariance = transition @ covariance @ transition.T + innovation
        if t >= 2:
            observe(increments[t], np.array([0, 0, law.return_loading, 0]), law.return_noise**2)
        if score is not None:
            observe(score[t], np.array([-1., 0, 0, law.score_noise]), 0.)
        means[t], variances[t] = mean[0], max(0., covariance[0, 0])
    return means, variances


def terminal_law(state_means: np.ndarray, state_variances: np.ndarray, horizon: int, law: GaussianLaw) -> tuple[np.ndarray, np.ndarray]:
    """Law of log P[t+H+1]-log P[t+1], excluding the pre-entry increment.

    Conditional on s_t, sum future AR innovations with their geometric
    loadings; then integrate over the observed-history posterior of s_t.
    """
    law.validate()
    means, variances = np.asarray(state_means, float), np.asarray(state_variances, float)
    if (type(horizon) is not int or horizon < 1 or means.ndim != 1 or means.shape != variances.shape
            or not len(means) or not np.isfinite(means).all() or not np.isfinite(variances).all()
            or np.any(variances < 0)):
        raise ValueError("require matched finite posterior vectors, nonnegative variance and positive integer horizon")
    phi = law.persistence
    geometric = np.cumsum(phi**np.arange(horizon))
    loading = law.return_loading*geometric[-1]
    future_variance = (horizon*law.return_noise**2
                       + law.return_loading**2*(1-phi**2)*np.sum(geometric[:-1]**2))
    return loading*means, future_variance+loading**2*variances


def normal_loss(means: np.ndarray, variances: np.ndarray, outcomes: np.ndarray) -> np.ndarray:
    means, variances, outcomes = (np.asarray(v, float) for v in (means, variances, outcomes))
    if (means.ndim != 1 or means.shape != variances.shape or means.shape != outcomes.shape
            or not len(means) or not all(np.isfinite(v).all() for v in (means, variances, outcomes))
            or np.any(variances <= 0)):
        raise ValueError("require matched finite Gaussian forecasts/outcomes and positive variance")
    sd = np.sqrt(variances)
    z = (outcomes-means)/sd
    error = np.fromiter((math.erf(float(v)/math.sqrt(2)) for v in z), float, count=len(z))
    return sd*(z*error+math.sqrt(2/math.pi)*np.exp(-z*z/2)-1/math.sqrt(math.pi))
