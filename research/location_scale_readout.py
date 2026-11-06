"""Continuous mean/scale research decoder with separate empirical calibration.

This is an estimator, not a calibrated confidence procedure or an information
oracle. Inputs are already transformed using fitting data only by its caller.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


RIDGE = .1
LOG_VARIANCE_BOUND = 6.
RELATIVE_VARIANCE_FLOOR = 1e-8
ABSOLUTE_VARIANCE_FLOOR = 1e-12


def empirical_loss(samples, locations, scales, observed):
    """Exact empirical CRPS, vectorized over arbitrary leading model axes.

    Forecast atoms are location + scale * calibration_residual. Merge sorting
    samples and queries avoids a quadratic sample/query distance tensor.
    """
    samples, locations, scales, observed = (np.asarray(x, float) for x in (samples, locations, scales, observed))
    if (samples.ndim < 1 or locations.ndim < 1 or not samples.shape[-1]
            or samples.shape[:-1] != locations.shape[:-1] or locations.shape != scales.shape
            or not locations.shape[-1] or np.any(scales <= 0)
            or not all(np.isfinite(x).all() for x in (samples, locations, scales, observed))):
        raise ValueError("require finite matching model axes, positive scales and nonempty forecast samples")
    try:
        query = np.broadcast_to(observed, locations.shape)
    except ValueError as error:
        raise ValueError("outcomes must cover the common query support") from error
    query = (query-locations)/scales
    shape, size, queries = samples.shape[:-1], samples.shape[-1], query.shape[-1]
    atoms = np.sort(samples, axis=-1).reshape(-1, size)
    y = query.reshape(-1, queries)
    combined = np.concatenate((atoms, y), axis=-1)
    order = np.argsort(combined, axis=-1, kind="stable")
    sorted_values = np.take_along_axis(combined, order, axis=-1)
    sample_mask = order < size
    count = np.cumsum(sample_mask, axis=-1)
    total = np.cumsum(np.where(sample_mask, sorted_values, 0.), axis=-1)
    inverse = np.empty_like(order)
    np.put_along_axis(inverse, order, np.broadcast_to(np.arange(size+queries), order.shape), axis=-1)
    positions = inverse[:, size:]
    left_count = np.take_along_axis(count, positions, axis=-1)
    left_sum = np.take_along_axis(total, positions, axis=-1)
    absolute = (y*left_count-left_sum+atoms.sum(axis=-1, keepdims=True)-left_sum-y*(size-left_count))/size
    pair_half = np.sum((2*np.arange(size)-size+1)*atoms, axis=-1, keepdims=True)/size**2
    return scales*np.maximum(absolute-pair_half, 0.).reshape(*shape, queries)


@dataclass(frozen=True)
class MeanScaleFit:
    feature_mean: np.ndarray
    outcome_mean: float
    mean_coefficients: np.ndarray
    scale_coefficients: np.ndarray

    def predict(self, features):
        features = np.asarray(features, float)
        if (features.ndim < 2 or features.shape[:-2] != self.feature_mean.shape[:-1]
                or features.shape[-1] != self.feature_mean.shape[-1] or not np.isfinite(features).all()):
            raise ValueError("prediction features require matching finite model axes")
        centered = features-self.feature_mean[..., None, :]
        location = self.outcome_mean+np.einsum("...np,...p->...n", centered, self.mean_coefficients)
        log_variance_shape = np.einsum("...np,...p->...n", centered, self.scale_coefficients)
        scale = np.exp(.5*np.clip(log_variance_shape, -LOG_VARIANCE_BOUND, LOG_VARIANCE_BOUND))
        return location, scale


def fit_mean_scale(features, outcomes):
    """Mean-square ridge mean; ridge log-squared-fit-residual scale shape.

    Both regressions use fitting data only, with unpenalized intercepts. The
    log-scale intercept is absorbed into the later residual distribution.
    """
    features, outcomes = np.asarray(features, float), np.asarray(outcomes, float)
    if (features.ndim < 2 or not features.shape[-1] or features.shape[-2] < 4
            or outcomes.shape != (features.shape[-2],) or not np.isfinite(features).all()
            or not np.isfinite(outcomes).all()):
        raise ValueError("fit requires finite features and identical nonempty outcome support")
    center = features.mean(axis=-2)
    x = features-center[..., None, :]
    ymean = float(outcomes.mean())
    gram = np.einsum("...np,...nq->...pq", x, x)/len(outcomes)+RIDGE*np.eye(features.shape[-1])
    rhs = np.einsum("...np,n->...p", x, outcomes-ymean)/len(outcomes)
    mean_beta = np.linalg.solve(gram, rhs[..., None])[..., 0]
    residual = outcomes-ymean-np.einsum("...np,...p->...n", x, mean_beta)
    floor = max(float(np.mean((outcomes-ymean)**2))*RELATIVE_VARIANCE_FLOOR, ABSOLUTE_VARIANCE_FLOOR)
    log_squared = np.log(np.maximum(residual**2, floor))
    scale_rhs = np.einsum("...np,...n->...p", x, log_squared-log_squared.mean(axis=-1, keepdims=True))/len(outcomes)
    scale_beta = np.linalg.solve(gram, scale_rhs[..., None])[..., 0]
    return MeanScaleFit(center, ymean, mean_beta, scale_beta)


def calibration_residuals(model, features, outcomes):
    """Separate calibration values never refit mean/scale coefficients."""
    location, scale = model.predict(features)
    outcomes = np.asarray(outcomes, float)
    if outcomes.shape != (location.shape[-1],) or not np.isfinite(outcomes).all():
        raise ValueError("calibration outcomes must cover the same finite support")
    return np.sort((outcomes-location)/scale, axis=-1)
