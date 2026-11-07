"""Pure loss/selection contract for a synthetic panel experiment.

Callers own timestamp, provenance and panel-identity validation. These functions
never declare financial suitability or aggregate different outcome cells.
"""

import numpy as np


def _losses(values):
    values = np.asarray(values, dtype=float)
    if not values.size or not np.isfinite(values).all() or np.any(values < 0):
        raise ValueError("losses must be nonempty, finite and nonnegative")
    return values


def normalize_gain(reference_loss, candidate_loss):
    """100*(R-C)/(R+C), with zero/zero=0 and NumPy broadcasting.

    Rescaling before arithmetic avoids overflow for large finite losses.
    """
    reference, candidate = np.broadcast_arrays(_losses(reference_loss), _losses(candidate_loss))
    scale = np.maximum(reference, candidate)
    reference = np.divide(reference, scale, out=np.zeros_like(scale), where=scale > 0)
    candidate = np.divide(candidate, scale, out=np.zeros_like(scale), where=scale > 0)
    denominator = reference + candidate
    return 100 * np.divide(reference - candidate, denominator,
                           out=np.zeros_like(denominator), where=denominator > 0)


def _panel(reference, candidate):
    reference, candidate = _losses(reference), _losses(candidate)
    if (reference.ndim != 3 or candidate.ndim != 4
            or candidate.shape[:2] != reference.shape[:2]
            or candidate.shape[-1] != reference.shape[-1]):
        raise ValueError("require reference[world,cell,origin] and candidate[world,cell,candidate,origin] on identical support")
    return reference, candidate


def _mean(values, axis):
    return (values / values.shape[axis]).sum(axis=axis)


def select_global(reference, candidate):
    """Select once after equal-world averages of within-world mean proper loss."""
    reference, candidate = _panel(reference, candidate)
    reference_means = _mean(_mean(reference, -1), 0)
    candidate_means = _mean(_mean(candidate, -1), 0)
    gains = normalize_gain(reference_means[:, None], candidate_means)
    selected = int(np.argmax(gains))
    cell, candidate_index = (int(i) for i in np.unravel_index(selected, gains.shape))
    return {"selected_cell": cell, "selected_candidate": candidate_index,
            "selected_index": selected, "reference_mean": float(reference_means[cell]),
            "candidate_mean": float(candidate_means[cell, candidate_index]),
            "gain": float(gains[cell, candidate_index]), "gain_matrix": gains,
            "reference_means": reference_means, "candidate_means": candidate_means}


def score_selection(reference, candidate, cell, candidate_index):
    """Return paired raw mean-loss improvement per world for one frozen choice."""
    reference, candidate = _panel(reference, candidate)
    if (type(cell) is not int or type(candidate_index) is not int
            or not 0 <= cell < reference.shape[1]
            or not 0 <= candidate_index < candidate.shape[2]):
        raise ValueError("selection indices must be in-range Python integers")
    return _mean(reference[:, cell], -1) - _mean(candidate[:, cell, candidate_index], -1)


def promotion_decision(pvalue, raw_reference_mean, raw_candidate_mean, alpha=.05):
    """Synthetic declaration only: CRT rejection AND strictly positive raw gain."""
    if (np.ndim(pvalue) != 0 or np.ndim(alpha) != 0
            or not np.isfinite(pvalue) or not np.isfinite(alpha)
            or not 0 <= pvalue <= 1 or not 0 < alpha < 1):
        raise ValueError("require finite pvalue in [0,1] and alpha in (0,1)")
    reference, candidate = _losses(raw_reference_mean), _losses(raw_candidate_mean)
    if reference.ndim or candidate.ndim:
        raise ValueError("declaration requires scalar raw mean losses")
    raw_gain = float(reference - candidate)
    reject, positive = bool(pvalue <= alpha), bool(raw_gain > 0)
    return {"crt_reject": reject, "positive_gain": positive,
            "promote": reject and positive, "raw_gain": raw_gain}
