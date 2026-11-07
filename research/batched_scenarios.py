"""Batch-equivalent synthetic generators; no changes to the frozen parent law."""

import numpy as np

from .search_qualification import NULLS, POSITIVES, SearchConfig


def _indices(seed, domain, indices):
    if (type(seed) is not int or seed < 0 or type(domain) is not int or domain < 0
            or not isinstance(indices, list) or not indices
            or any(type(i) is not int or i < 0 for i in indices)
            or len(set(indices)) != len(indices)):
        raise ValueError("require nonnegative integer seed/domain and distinct nonnegative integer world indices")


def _ar(values, persistence):
    """Update [world,time,column] white noise with the parent's exact arithmetic."""
    for t in range(1, values.shape[1]):
        values[:, t] = persistence * values[:, t - 1] + np.sqrt(1 - persistence**2) * values[:, t]
    return values


def worlds(config: SearchConfig, domain: int, indices: list[int], kind: str):
    """Return prices[W,N], contexts[W,N,2], scores[W,N,C], scalar-stream exact."""
    config.validate()
    _indices(config.seed, domain, indices)
    if kind not in (*NULLS, *POSITIVES):
        raise ValueError("unknown declared world family")
    size, candidates = config.steps, config.candidates
    states, innovations, volatilities, tails, common, own, positive = ([] for _ in range(7))
    for index in indices:
        rng = np.random.default_rng(np.random.SeedSequence([config.seed, domain, index]))
        states.append(rng.normal(size=(size, 1)))
        innovations.append(rng.normal(size=size))
        if kind == "clustered_t3_p95":
            volatilities.append(rng.normal(size=(size, 1)))
            tails.append(rng.standard_t(3, size=size))
        # These draws are consumed even when the positive-family scores overwrite
        # them. Skipping them would silently change the parent's random stream.
        common.append(rng.normal(size=(size, 1)))
        own.append(rng.normal(size=(size, candidates)))
        if kind in POSITIVES:
            positive.append(rng.normal(size=(size, candidates)))
    state = _ar(np.stack(states), .95)[:, :, 0]
    innovation = np.stack(innovations)
    if kind == "clustered_t3_p95":
        volatility = np.where(_ar(np.stack(volatilities), .97)[:, :, 0] > 0, .08, .02)
        increments = np.stack(tails) / np.sqrt(3) * volatility
    else:
        increments = .04 * innovation
        if kind == "leading_location":
            increments[:, 2:] += .08 * state[:, :-2]
        elif kind == "leading_scale":
            increments[:, 2:] = np.where(state[:, :-2] > 0, .10, .02) * innovation[:, 2:]
    price = np.cumsum(increments, axis=1)
    persistence = .5 if kind == "gaussian_p50" else .95
    scores = .7 * _ar(np.stack(common), persistence) + .7 * _ar(np.stack(own), persistence)
    if kind in POSITIVES:
        scores = -state[:, :, None] + _ar(np.stack(positive), .5) * np.linspace(.1, 2, candidates)
    context = np.zeros((len(indices), size, 2))
    if size > 12:
        context[:, 12:, 0] = price[:, 12:] - price[:, :-12]
        windows = np.lib.stride_tricks.sliding_window_view(increments, 12, axis=1)
        context[:, 12:, 1] = np.std(windows[:, 1:], axis=-1, ddof=1)
    return price, context, scores


def null_scores(seed: int, domain: int, indices: list[int], contexts, candidates: int = 24):
    """Exact batch of scalar redraw_scores(rng, context, 1, C, .5)[0]."""
    _indices(seed, domain, indices)
    contexts = np.asarray(contexts, float)
    if (type(candidates) is not int or candidates < 1 or contexts.ndim != 3
            or contexts.shape[0] != len(indices) or contexts.shape[1] < 1
            or contexts.shape[2] != 2 or not np.isfinite(contexts).all()):
        raise ValueError("require finite contexts[world,time,2] and positive candidate count")
    size = contexts.shape[1]
    common, independent = [], []
    for index in indices:
        rng = np.random.default_rng(np.random.SeedSequence([seed, domain, index]))
        common.append(rng.normal(size=(size, 1, 1))[:, 0])
        independent.append(rng.normal(size=(size, 1, candidates))[:, 0])
    values = -_ar(np.stack(common), .95) + _ar(np.stack(independent), .5) * np.linspace(.1, 2, candidates)
    return values + .5 * contexts[:, :, 0, None]
