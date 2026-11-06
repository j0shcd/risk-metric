"""Fixed finite-bin distribution readout for exploratory research, not a model gate."""

from __future__ import annotations

import numpy as np


def weighted_crps(samples: np.ndarray, weights: np.ndarray, outcome: float) -> float:
    """Exact CRPS of a discrete probability distribution (including tied atoms)."""
    samples, weights = np.asarray(samples, float), np.asarray(weights, float)
    if (samples.ndim != 1 or samples.shape != weights.shape or not len(samples)
            or not np.isfinite(samples).all() or not np.isfinite(weights).all()
            or not np.isfinite(outcome) or np.any(weights < 0)
            or not np.isclose(weights.sum(), 1, rtol=0, atol=1e-12)):
        raise ValueError("require finite atoms and nonnegative probability weights summing to one")
    order = np.argsort(samples)
    x, w = samples[order], weights[order]
    previous_w = np.cumsum(w) - w
    previous_wx = np.cumsum(w * x) - w * x
    half_pair = np.sum(w * (x * previous_w - previous_wx))
    return float(max(0., np.sum(w * np.abs(x - outcome)) - half_pair))


def mixture_forecasts(fit: np.ndarray, calibration: np.ndarray, query: np.ndarray) -> dict:
    """Two fixed median context bins; optional third column is an indicator.

    Both forecasts mix equally with the pooled distribution. Empty indicator
    cells fall back exactly to the reference. Thus a duplicate context split
    cannot change shrinkage merely by adding another hierarchy level.
    Bin thresholds use fit FEATURES only; probability atoms come
    from a distinct later calibration phase. This is a particular decoder, not
    a universal measure of information or a calibrated confidence interval.
    """
    fit, calibration, query = np.asarray(fit, float), np.asarray(calibration, float), np.asarray(query, float)
    if (fit.ndim != 2 or fit.shape[1] not in (2, 3) or not len(fit)
            or calibration.ndim != 2 or calibration.shape[1] != fit.shape[1]
            or not len(calibration) or query.shape != (fit.shape[1],)
            or not all(np.isfinite(x).all() for x in (fit, calibration, query))):
        raise ValueError("readout needs common finite feature support")
    cuts = np.median(fit, axis=0)
    bins, query_bin = calibration > cuts, query > cuts
    context = np.all(bins[:, :2] == query_bin[:2], axis=1)
    pooled = np.full(len(calibration), 1 / len(calibration))
    reference = .5 * pooled + .5 * context / context.sum() if context.any() else pooled
    cell = context.copy()
    if fit.shape[1] == 3:
        cell &= bins[:, 2] == query_bin[2]
        candidate = .5 * pooled + .5 * cell / cell.sum() if cell.any() else reference.copy()
    else:
        candidate = reference.copy()
    return {"reference": reference, "candidate": candidate, "thresholds": cuts.tolist(),
            "context_cell_n": int(context.sum()), "candidate_cell_n": int(cell.sum()),
            "context_fallback": not bool(context.any()), "candidate_fallback": not bool(cell.any())}


def distribution_summary(samples: np.ndarray, weights: np.ndarray) -> dict:
    """Left-continuous inverse empirical CDF; retained atoms reproduce forecasts."""
    order = np.argsort(samples)
    x, w = np.asarray(samples)[order], np.asarray(weights)[order]
    cdf = np.cumsum(w)
    return {f"q{int(q * 100)}": float(x[min(int(np.searchsorted(cdf, q)), len(x) - 1)])
            for q in (.1, .5, .9)}
