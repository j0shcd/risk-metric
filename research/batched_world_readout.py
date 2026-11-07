"""Independent-world batching of the synthetic location/scale readout.

No information is pooled between worlds; only a caller may combine their losses.
Estimable features match the frozen scalar decoder. Exact constant fit columns
are canonicalized rather than amplifying its floating-point projection residuals.
"""

from dataclasses import dataclass

import numpy as np

from .location_scale_readout import (
    ABSOLUTE_VARIANCE_FLOOR, LOG_VARIANCE_BOUND, RELATIVE_VARIANCE_FLOOR, RIDGE,
)
from .location_scale_search import INDICATOR_RESIDUAL_TOLERANCE, PROJECTION_RCOND


def canonical_score_columns(scores, fit):
    """Constant nonzero floats can have a tiny computed std; they carry no variation."""
    scores = np.asarray(scores, float)
    constant = np.ptp(scores[..., fit, :], axis=-2) == 0
    return np.where(constant[..., None, :], 0., scores)


def world_features(context, scores, indices):
    """Fit transforms per world and return the four phase feature arrays."""
    context, scores = np.asarray(context, float), np.asarray(scores, float)
    if (context.ndim != 3 or context.shape[-1] != 2 or scores.ndim != 3
            or scores.shape[:2] != context.shape[:2] or min(scores.shape) < 1
            or not np.isfinite(context).all() or not np.isfinite(scores).all()
            or len(indices) != 4):
        raise ValueError("require finite [world,time,2] context, matching scores and four phases")
    phases = []
    for phase in indices:
        phase = np.asarray(phase)
        if (phase.ndim != 1 or not len(phase) or not np.issubdtype(phase.dtype, np.integer)
                or np.any(phase < 0) or np.any(phase >= context.shape[1])):
            raise ValueError("phases require nonempty valid integer indices")
        phases.append(phase)
    fit = phases[0]
    scores = canonical_score_columns(scores, fit)
    center, raw_context_scale = context[:, fit].mean(axis=1), context[:, fit].std(axis=1)
    context_scale = np.where(raw_context_scale > 0, raw_context_scale, 1.)
    normalized = (context - center[:, None]) / context_scale[:, None]
    design = np.concatenate((np.ones((len(context), len(fit), 1)), normalized[:, fit]), axis=-1)
    projection = np.einsum("wpn,wnc->wcp", np.linalg.pinv(design, rcond=PROJECTION_RCOND), scores[:, fit])
    predicted_fit = np.einsum("wnp,wcp->wnc", design, projection)
    raw_indicator_scale = (scores[:, fit] - predicted_fit).std(axis=1)
    score_scale = scores[:, fit].std(axis=1)
    active = raw_indicator_scale > INDICATOR_RESIDUAL_TOLERANCE * np.maximum(score_scale, 1e-12)
    indicator_scale = np.where(active, raw_indicator_scale, 1.)
    reference, candidate = [], []
    worlds, _, candidates = scores.shape
    for phase in phases:
        z = normalized[:, phase]
        phase_design = np.concatenate((np.ones((worlds, len(phase), 1)), z), axis=-1)
        projected = np.einsum("wnp,wcp->wnc", phase_design, projection)
        residual = np.where(active[:, None], (scores[:, phase] - projected) / indicator_scale[:, None], 0.)
        reference.append(z[:, None])
        candidate.append(np.concatenate((np.broadcast_to(z[:, None], (worlds, candidates, len(phase), 2)),
                                         residual.transpose(0, 2, 1)[..., None]), axis=-1))
    transforms = {"context_center": center, "context_scale": context_scale, "projection": projection,
                  "indicator_scale": indicator_scale, "active": active}
    return reference, candidate, transforms


@dataclass(frozen=True)
class WorldFit:
    feature_mean: np.ndarray
    outcome_mean: np.ndarray
    mean_coefficients: np.ndarray
    scale_coefficients: np.ndarray

    def predict(self, query):
        query = np.asarray(query, float)
        if (query.ndim != 4 or query.shape[:2] != self.feature_mean.shape[:2]
                or query.shape[-1] != self.feature_mean.shape[-1] or not np.isfinite(query).all()):
            raise ValueError("query must match world, model and finite feature axes")
        centered = query - self.feature_mean[:, :, None]
        location = self.outcome_mean[:, None, None] + np.einsum("wcnp,wcp->wcn", centered, self.mean_coefficients)
        log_shape = np.einsum("wcnp,wcp->wcn", centered, self.scale_coefficients)
        scale = np.exp(.5 * np.clip(log_shape, -LOG_VARIANCE_BOUND, LOG_VARIANCE_BOUND))
        return location, scale


def fit_mean_scale_worlds(features, outcomes):
    features, outcomes = np.asarray(features, float), np.asarray(outcomes, float)
    if (features.ndim != 4 or min(features.shape) < 1 or features.shape[2] < 4
            or outcomes.shape != (features.shape[0], features.shape[2])
            or not np.isfinite(features).all() or not np.isfinite(outcomes).all()):
        raise ValueError("fit needs finite [world,model,row,feature] and matching outcomes")
    n = features.shape[2]
    center = features.mean(axis=2)
    x = features - center[:, :, None]
    ymean = outcomes.mean(axis=1)
    gram = np.einsum("wcnp,wcnq->wcpq", x, x) / n + RIDGE * np.eye(features.shape[-1])
    rhs = np.einsum("wcnp,wn->wcp", x, outcomes - ymean[:, None]) / n
    beta = np.linalg.solve(gram, rhs[..., None])[..., 0]
    residual = outcomes[:, None] - ymean[:, None, None] - np.einsum("wcnp,wcp->wcn", x, beta)
    floor = np.maximum(np.mean((outcomes-ymean[:, None])**2, axis=1) * RELATIVE_VARIANCE_FLOOR,
                       ABSOLUTE_VARIANCE_FLOOR)
    log_squared = np.log(np.maximum(residual**2, floor[:, None, None]))
    scale_rhs = np.einsum("wcnp,wcn->wcp", x, log_squared-log_squared.mean(axis=-1, keepdims=True)) / n
    scale_beta = np.linalg.solve(gram, scale_rhs[..., None])[..., 0]
    return WorldFit(center, ymean, beta, scale_beta)


def calibration_residuals_worlds(model, features, outcomes):
    location, scale = model.predict(features)
    outcomes = np.asarray(outcomes, float)
    if outcomes.shape != (location.shape[0], location.shape[-1]) or not np.isfinite(outcomes).all():
        raise ValueError("calibration outcomes must match world and row axes")
    return np.sort((outcomes[:, None] - location) / scale, axis=-1)
