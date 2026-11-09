"""Frozen Gaussian worlds and current-signal oracles for the readout audit.

Only the snapshot and released feature arrays are inputs to the decoder. Oracle
futures use independent streams, never the realized future price/state suffix.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .market_dataset import COMPONENTS, digest

PHI = .8
MU = .1
SIGMA = .6
AUDIT_SEED = 2026110901
ENGINEERING_SEED = 93117
FIRST_QUERY = pd.Timestamp('2014-12-31')


def rng(root_seed, world_id, stream_id, query_index=0, bank=0):
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence(
        [root_seed, world_id, stream_id, query_index, bank])))


def _states(generator, n):
    innovations = generator.standard_normal(n)
    states = np.empty(n)
    states[0] = innovations[0]
    for i in range(1, n):
        states[i] = PHI * states[i - 1] + math.sqrt(1 - PHI**2) * innovations[i]
    return states


def make_world(world_id, beta, root_seed=AUDIT_SEED):
    """Generate all daily prices and 97 released scalars; no scoring occurs."""
    if beta not in (0., .15):
        raise ValueError('beta must be a registered loading')
    dates = pd.date_range('2012-01-01', '2022-12-31', freq='D')
    months = pd.period_range('2012-01', '2023-01', freq='M')
    month_index = months.get_indexer(dates.to_period('M'))
    states = _states(rng(root_seed, world_id, 1), len(months))
    nuisance = _states(rng(root_seed, world_id, 3), len(months))
    noise = rng(root_seed, world_id, 2).standard_normal(len(dates) - 1)
    increments = (MU / 365 + beta * states[month_index[1:]] / dates[1:].days_in_month
                  + SIGMA / math.sqrt(365) * noise)
    logs = np.r_[0., np.cumsum(increments)]
    queries = pd.date_range(FIRST_QUERY, '2022-12-31', freq='ME')
    forthcoming = months.get_indexer(queries.to_period('M') + 1)
    features = {'constant': np.zeros(len(queries)), 'nuisance': nuisance[forthcoming],
                'exact': states[forthcoming]}
    features['noisy'] = features['exact'] + rng(root_seed, world_id, 4).standard_normal(len(queries))
    metadata = {'world_id': world_id, 'beta': beta, 'root_seed': root_seed}
    snapshot = {'schema': 'retrospective-btc-snapshot-v1', 'source_sha256': digest(metadata),
                'availability': 'synthetic scalars released after month-end close',
                'daily': [{'date': d.date().isoformat(), 'price': float(p)}
                          for d, p in zip(dates, np.exp(logs))],
                'monthly': [{'date': d.date().isoformat(), **dict.fromkeys(COMPONENTS, 0.)}
                            for d in queries]}
    return {'snapshot': snapshot, 'features': features, 'metadata': metadata,
            'dates': dates, 'log_prices': logs}


def price_posteriors(world):
    """Full-price-history filter, returned prior is for forthcoming month state."""
    # Read actual snapshot prices, not privileged latent states or cached prices.
    rows = world['snapshot']['daily']
    dates = pd.DatetimeIndex([r['date'] for r in rows])
    logs = np.log(np.array([r['price'] for r in rows]))
    beta = world['metadata']['beta']
    queries = {r['date'] for r in world['snapshot']['monthly']}
    result = {}
    mean, variance = 0., 1.
    for month in dates.to_period('M').unique():
        indexes = np.flatnonzero(dates.to_period('M') == month)
        # Jan 1 is an initial level; its first observed increment is Jan 2.
        increment_indexes = indexes[indexes > 0]
        n = len(increment_indexes)
        observed = float(np.sum(logs[increment_indexes] - logs[increment_indexes - 1])) - n * MU / 365
        loading = beta * n / month.days_in_month
        noise_variance = SIGMA**2 * n / 365
        gain = variance * loading / (loading**2 * variance + noise_variance)
        mean += gain * (observed - loading * mean)
        variance *= 1 - gain * loading
        mean, variance = PHI * mean, PHI**2 * variance + 1 - PHI**2
        query = dates[indexes[-1]].date().isoformat()
        if query in queries:
            result[query] = (float(mean), float(variance))
    return result


def conditional_posterior(prior, feature, value):
    mean, variance = prior
    if feature in ('constant', 'nuisance', 'price_only'):
        return prior
    if feature == 'exact':
        return (float(value), 0.)
    if feature == 'noisy':
        gain = variance / (variance + 1)
        return (float(mean + gain * (value - mean)), float(variance / (variance + 1)))
    raise ValueError('unknown feature')


def _future_calendar(query, horizon):
    query = pd.Timestamp(query)
    if query != query + pd.offsets.MonthEnd(0) or horizon < 1:
        raise ValueError('require month-end query and positive horizon')
    entry = query + pd.Timedelta(days=1)
    end = entry + pd.DateOffset(months=horizon)
    # Entry's price increment cancels from every outcome; initial path is zero.
    dates = pd.date_range(entry + pd.Timedelta(days=1), end, freq='D')
    month_index = (dates.year - entry.year) * 12 + dates.month - entry.month
    return dates, np.asarray(month_index, int)


def terminal_moments(query, horizon, beta, posterior):
    dates, month_index = _future_calendar(query, horizon)
    coefficients = beta * np.bincount(month_index, weights=1 / dates.days_in_month,
                                      minlength=horizon + 1)
    powers = PHI ** np.arange(horizon + 1)
    mean, variance = posterior
    terminal_mean = len(dates) * MU / 365 + coefficients @ powers * mean
    # Each future state innovation has its own coefficient in terminal return.
    initial_loading = coefficients @ powers
    innovation_loadings = [coefficients[k:] @ powers[:horizon + 1 - k]
                           for k in range(1, horizon + 1)]
    terminal_variance = (SIGMA**2 * len(dates) / 365 + initial_loading**2 * variance
                         + (1 - PHI**2) * np.sum(np.square(innovation_loadings)))
    return float(terminal_mean), float(terminal_variance)


def simulate_outcomes(query, horizon, beta, posterior, world_id, bank,
                      root_seed=AUDIT_SEED, paths=128):
    """Finite issued forecasts; common normals across posterior information sets."""
    dates, month_index = _future_calendar(query, horizon)
    q = pd.Timestamp(query)
    query_index = (q.year - FIRST_QUERY.year) * 12 + q.month - FIRST_QUERY.month
    generator = rng(root_seed, world_id, 5, query_index, bank)
    normals = generator.standard_normal((paths, horizon + 1))
    states = np.empty_like(normals)
    states[:, 0] = posterior[0] + math.sqrt(posterior[1]) * normals[:, 0]
    for i in range(1, horizon + 1):
        states[:, i] = PHI * states[:, i - 1] + math.sqrt(1 - PHI**2) * normals[:, i]
    increments = (MU / 365 + beta * states[:, month_index] / np.asarray(dates.days_in_month)
                  + SIGMA / math.sqrt(365) * generator.standard_normal((paths, len(dates))))
    path = np.column_stack((np.zeros(paths), np.cumsum(increments, axis=1)))
    return np.column_stack((path[:, -1], -path.min(axis=1),
                            (np.maximum.accumulate(path, axis=1) - path).max(axis=1)))


def gaussian_crps(mean, variance, outcome):
    if variance < 0:
        raise ValueError('negative variance')
    if variance == 0:
        return abs(outcome - mean)
    scale = math.sqrt(variance)
    z = (outcome - mean) / scale
    cdf = .5 * (1 + math.erf(z / math.sqrt(2)))
    density = math.exp(-.5 * z*z) / math.sqrt(2 * math.pi)
    return scale * (z * (2*cdf - 1) + 2*density - 1/math.sqrt(math.pi))
