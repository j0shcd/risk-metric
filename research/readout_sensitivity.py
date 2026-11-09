"""Registered diagnostic of an unchanged empirical-CDF readout; no promotion.

Freeze implementation before `run`. Audit worlds are fixed by the registration;
engineering tests use a separate seed. No browser, network or production writes.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import platform
import time

import numpy as np
import pandas as pd

from . import readout_synthetic_world as world_law
from .distribution_readout import distribution_summary, weighted_crps
from .market_dataset import TARGETS, canonical_bytes
from .market_information import score_candidate

REGISTRATION = 'docs/artifacts/direct-cdf-sensitivity-2026-11-09-registration.json'
REGISTRATION_SHA = '423265ed2494247b1ce5ae8e1f357bc48cf1880c27bf3a9903ecee692372501f'
ARMS = ('constant', 'nuisance', 'noisy', 'exact')
METRICS = ('crps', 'brier', 'coverage80', 'width80')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def runtime():
    return {'python': platform.python_version(), 'numpy': np.__version__, 'pandas': pd.__version__}


def root_path():
    return Path(__file__).resolve().parents[1]


def registration():
    payload = (root_path() / REGISTRATION).read_bytes()
    if sha(payload) != REGISTRATION_SHA:
        raise ValueError('registration changed; no silent redesign')
    spec = json.loads(payload)
    for name, expected in spec['frozen_code_sha256'].items():
        if sha((root_path() / 'research' / name).read_bytes()) != expected:
            raise ValueError('frozen market benchmark code changed: ' + name)
    return spec


def implementation():
    names = [REGISTRATION, 'research/readout_sensitivity.py', 'research/readout_synthetic_world.py',
             'tests/test_readout_sensitivity.py', 'tests/test_readout_synthetic_world.py']
    return {name: sha((root_path() / name).read_bytes()) for name in names}


def freeze(path):
    registration()
    payload = canonical_bytes({'schema': 'readout-sensitivity-implementation-v1',
                               'code_sha256': implementation(), 'runtime': runtime()})
    with Path(path).open('xb') as stream:
        stream.write(payload)
    return sha(payload)


def verify_freeze(path):
    spec = registration()
    payload = Path(path).read_bytes()
    frozen = json.loads(payload)
    if frozen['code_sha256'] != implementation() or frozen['runtime'] != runtime():
        raise ValueError('implementation/runtime changed after freeze')
    return spec, sha(payload)


def event_mask(atoms, target):
    return np.asarray(atoms) < 0 if target == TARGETS[0] else np.asarray(atoms) > math.log(2)


def empirical_metrics(atoms, weights, observed, target, crps):
    atoms, weights = np.asarray(atoms), np.asarray(weights)
    quantiles = distribution_summary(atoms, weights)
    probability = float(weights @ event_mask(atoms, target))
    event = bool(event_mask([observed], target)[0])
    lo, hi = quantiles['q10'], quantiles['q90']
    return {'crps': float(crps), 'brier': float((probability - event)**2),
            'coverage80': float(lo <= observed <= hi), 'width80': float(hi-lo)}


def normal_metrics(mean, variance, observed):
    sd = math.sqrt(variance)
    probability = .5 * (1 + math.erf(-mean / (sd * math.sqrt(2))))
    half_width = 1.2815515655446004 * sd
    return {'crps': float(world_law.gaussian_crps(mean, variance, observed)),
            'brier': float((probability - (observed < 0))**2),
            'coverage80': float(mean-half_width <= observed <= mean+half_width),
            'width80': float(2*half_width)}


def candidate(world, arm):
    return {'name': arm, 'direction': 'undirected', 'provenance': 'registered synthetic law; released at decision',
            'values': [{'date': row['date'], 'value': float(value)}
                       for row, value in zip(world['snapshot']['monthly'], world['features'][arm], strict=True)]}


def audit_world(world_id, beta, *, root_seed, paths):
    """All four arms share one realized world; call the frozen caller unchanged."""
    world = world_law.make_world(world_id, beta, root_seed=root_seed)
    results = {arm: score_candidate(world['snapshot'], candidate(world, arm)) for arm in ARMS}
    base = results['constant']
    support = [row['date'] for row in world['snapshot']['monthly']]
    expected_support = pd.date_range('2014-12-31', '2022-12-31', freq='ME').strftime('%Y-%m-%d').tolist()
    if support != expected_support:
        raise ValueError('wrong query calendar')
    for arm, result in results.items():
        if result['eligibility'] != base['eligibility'] or len(result['predictions']) != len(base['predictions']):
            raise ValueError('arm-specific support or eligibility')
        for row, reference in zip(result['predictions'], base['predictions'], strict=True):
            identity = ('date', 'horizon', 'target', 'role', 'status', 'outcome', 'train_dates', 'atoms', 'reference_weights')
            if any(row[key] != reference[key] for key in identity):
                raise ValueError('arm-specific outcome/training/reference')
            if row['train_last_label_available'] >= row['date']:
                raise ValueError('unmatured label admitted')
    # The benchmark has no scored four-year forecasts on these dates.
    scored = [[r for r in result['predictions'] if r['status'] == 'scored' and r['role'] == 'development']
              for result in results.values()]
    for horizon, expected in ((12, 48), (24, 24), (48, 0)):
        if any(sum(r['horizon'] == horizon and r['target'] == TARGETS[0] for r in records) != expected
               for records in scored):
            raise ValueError('scored-origin count differs from registration')
    posteriors = world_law.price_posteriors(world)
    oracle_cache = {}
    records = []
    for index, base_row in enumerate(scored[0]):
        date, horizon, target = base_row['date'], base_row['horizon'], base_row['target']
        observed = base_row['outcome']
        query_index = support.index(date)
        cache_key = (date, horizon)
        if cache_key not in oracle_cache:
            prior = posteriors[date]
            info = {'price': prior,
                    'noisy': world_law.conditional_posterior(prior, 'noisy', world['features']['noisy'][query_index]),
                    'exact': world_law.conditional_posterior(prior, 'exact', world['features']['exact'][query_index])}
            forecasts = {}
            for name, posterior in info.items():
                mean, variance = world_law.terminal_moments(date, horizon, beta, posterior)
                banks = [world_law.simulate_outcomes(date, horizon, beta, posterior, world_id, bank,
                                                     root_seed=root_seed, paths=paths) for bank in (0, 1)]
                forecasts[name] = {'mean': mean, 'variance': variance, 'banks': banks}
            oracle_cache[cache_key] = forecasts
        atoms = base_row['atoms']
        size = len(atoms)
        metrics = {
            'pooled': empirical_metrics(atoms, np.full(size, 1/size), observed, target, base_row['unconditional_crps']),
            'reference': empirical_metrics(atoms, base_row['reference_weights'], observed, target, base_row['reference_crps'])}
        arm_records = {}
        for arm, rows in zip(ARMS, scored, strict=True):
            row = rows[index]
            metrics[arm] = empirical_metrics(atoms, row['candidate_weights'], observed, target, row['candidate_crps'])
            weights = np.asarray(row['candidate_weights'])
            arm_records[arm] = {'weights': row['candidate_weights'], 'cell_n': row['candidate_cell_n'],
                                'fallback': row['candidate_fallback'], 'effective_atoms': float(1/(weights @ weights))}
        if metrics['constant'] != metrics['reference'] or arm_records['constant']['weights'] != base_row['reference_weights']:
            raise ValueError('constant split changed reference forecast')
        banks_record = {}
        target_index = TARGETS.index(target)
        for info_name, forecast in oracle_cache[cache_key].items():
            model = 'oracle_' + info_name
            if target_index == 0:
                metrics[model] = normal_metrics(forecast['mean'], forecast['variance'], observed)
            else:
                # Score the actual finite issued ensembles, without changing decoder CRPS.
                bank_metrics = []
                for bank in forecast['banks']:
                    samples = bank[:, target_index]
                    loss = weighted_crps(samples, np.full(len(samples), 1/len(samples)), observed)
                    bank_metrics.append(empirical_metrics(samples, np.full(len(samples), 1/len(samples)), observed, target, loss))
                metrics[model] = {m: float(np.mean([b[m] for b in bank_metrics])) for m in METRICS}
                banks_record[model] = bank_metrics
        records.append({'date': date, 'horizon': horizon, 'target': target, 'outcome': observed,
                        'atoms': atoms, 'reference_weights': base_row['reference_weights'], 'train_dates': base_row['train_dates'],
                        'context_cell_n': base_row['context_cell_n'], 'context_fallback': base_row['context_fallback'],
                        'outside_atom_range': not min(atoms) <= observed <= max(atoms),
                        'arms': arm_records, 'metrics': metrics, 'oracle_banks': banks_record,
                        'terminal_oracle_moments': {name: {'mean': f['mean'], 'variance': f['variance']}
                                                    for name, f in oracle_cache[cache_key].items()}})
    return {'world_id': world_id, 'beta': beta, 'root_seed': root_seed,
            'oracle_paths_per_bank': paths, 'oracle_banks': 2,
            'price_sha256': sha(np.asarray(world['log_prices'], dtype='<f8').tobytes()),
            'features': {name: np.asarray(v).tolist() for name, v in world['features'].items()},
            'eligibility': base['eligibility'], 'records': records}


def contrast_summary(values, indices):
    values = np.asarray(values, float)
    means = values[indices].mean(axis=1)
    return {'mean': float(values.mean()), 'pointwise_95_percentile_world_bootstrap': np.quantile(means, [.025, .975]).tolist(),
            'world_median': float(np.median(values)), 'world_q10_q90': np.quantile(values, [.1, .9]).tolist(),
            'world_positive_n': int(np.sum(values > 0)), 'world_n': len(values)}


def summarize(worlds, resamples, seed):
    cells = []
    budgets = {(w['oracle_paths_per_bank'], w['oracle_banks']) for w in worlds}
    if len(budgets) != 1:
        raise ValueError('mixed oracle simulation budgets')
    paths, banks = next(iter(budgets))
    by_beta = sorted({w['beta'] for w in worlds})
    for beta in by_beta:
        group = sorted((w for w in worlds if w['beta'] == beta), key=lambda w: w['world_id'])
        if len({w['world_id'] for w in group}) != len(group):
            raise ValueError('duplicate world ID')
        rng = np.random.default_rng(np.random.SeedSequence([seed, 0, 6, 0, 0]))
        indices = rng.integers(0, len(group), size=(resamples, len(group)))
        for horizon in (12, 24, 48):
            for target in TARGETS:
                matching = [[r for r in w['records'] if r['horizon'] == horizon and r['target'] == target] for w in group]
                counts = [len(rows) for rows in matching]
                cell = {'beta': beta, 'horizon': horizon, 'target': target, 'world_n': len(group), 'scored_origins_per_world': counts}
                if not any(counts):
                    cells.append({**cell, 'status': 'unavailable_by_registered_calendar'})
                    continue
                if len(set(counts)) != 1 or not all(counts):
                    raise ValueError('unequal world support; no silent denominator reduction')
                models = matching[0][0]['metrics'].keys()
                means = {model: {m: np.array([np.mean([r['metrics'][model][m] for r in rows]) for rows in matching])
                                 for m in METRICS} for model in models}
                cell['models'] = {model: {m: contrast_summary(v, indices) for m, v in ms.items()} for model, ms in means.items()}
                cell['contrasts'] = {}
                for arm in ARMS:
                    oracle_name = 'oracle_' + (arm if arm in ('noisy', 'exact') else 'price')
                    pairs = {'reference_minus_candidate': ('reference', arm), 'pooled_minus_candidate': ('pooled', arm),
                             'price_oracle_minus_signal_oracle': ('oracle_price', oracle_name),
                             'candidate_minus_signal_oracle': (arm, oracle_name)}
                    cell['contrasts'][arm] = {name: {m: contrast_summary(means[a][m]-means[b][m], indices) for m in METRICS}
                                              for name, (a, b) in pairs.items()}
                cell['diagnostics'] = {
                    arm: {'fallback_fraction': float(np.mean([r['arms'][arm]['fallback'] for rows in matching for r in rows])),
                          'cell_n_q0_q50_q100': np.quantile([r['arms'][arm]['cell_n'] for rows in matching for r in rows], [0, .5, 1]).tolist(),
                          'effective_atom_n_q10_q50_q90': np.quantile([r['arms'][arm]['effective_atoms'] for rows in matching for r in rows], [.1, .5, .9]).tolist()}
                    for arm in ARMS}
                cell['diagnostics']['outside_atom_range_fraction'] = float(np.mean([r['outside_atom_range'] for rows in matching for r in rows]))
                cell['oracle_bank_mean_absolute_discrepancy'] = {
                    model: {m: float(np.mean([abs(r['oracle_banks'][model][0][m]-r['oracle_banks'][model][1][m])
                                              for rows in matching for r in rows])) for m in METRICS}
                    for model in matching[0][0]['oracle_banks']}
                cells.append(cell)
    return {'schema': 'direct-cdf-sensitivity-results-v1', 'world_count': len(worlds), 'cells': cells,
            'intervals': 'pointwise95% whole-world percentile bootstrap; no simultaneous inference or promotion test',
            'oracle_paths_per_bank': paths, 'oracle_banks': banks,
            'oracle_downside': f'mean of {banks} finite{paths}-path issued-ensemble metrics, not exact ideal-law scores'}


def run(freeze_path, output):
    spec, identity = verify_freeze(freeze_path)
    output = Path(output)
    output.mkdir(exist_ok=False)
    budget = spec['budget']
    manifest = {'status': 'running', 'registration_sha256': REGISTRATION_SHA, 'implementation_freeze_sha256': identity,
                'runtime': runtime(), 'planned_worlds': budget['worlds_per_law']*len(spec['law']['monthly_loadings']), 'completed': [], 'failures': []}
    def save():
        (output/'manifest.json').write_bytes(canonical_bytes(manifest))
    save()
    (output/'implementation-freeze.json').write_bytes(Path(freeze_path).read_bytes())
    started = time.monotonic()
    worlds = []
    for world_id in budget['world_ids']:
        for beta in spec['law']['monthly_loadings']:
            if time.monotonic()-started > budget['wall_clock_cap_seconds']:
                manifest['status'] = 'incomplete_resource_cap'; save(); return manifest
            name = f'world-{world_id:03d}-beta-{beta:.2f}.json.gz'
            try:
                world = audit_world(world_id, beta, root_seed=spec['randomness']['root_seed'], paths=budget['oracle_paths_per_bank'])
                payload = canonical_bytes(world)
                # gzip mtime is fixed so complete replays have stable compressed bytes.
                (output/name).write_bytes(gzip.compress(payload, mtime=0))
                worlds.append(world)
                manifest['completed'].append({'file': name, 'sha256': sha(payload)})
                print(json.dumps({'world': world_id, 'beta': beta, 'completed': len(worlds), 'seconds': round(time.monotonic()-started, 1)}), flush=True)
                save()
            except Exception as error:
                manifest['status'] = 'incomplete_failure'
                manifest['failures'].append({'world_id': world_id, 'beta': beta, 'reason': f'{type(error).__name__}: {error}'})
                save()
                raise
    result = summarize(worlds, budget['bootstrap_world_resamples'], spec['randomness']['root_seed'])
    result['registration_sha256'] = REGISTRATION_SHA
    result['implementation_freeze_sha256'] = identity
    (output/'summary.json').write_bytes(canonical_bytes(result))
    manifest['status'] = 'complete'; manifest['seconds'] = time.monotonic()-started
    manifest['summary_sha256'] = sha((output/'summary.json').read_bytes()); save()
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['freeze', 'run'])
    parser.add_argument('--freeze', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.command == 'freeze':
        print(freeze(args.freeze))
    else:
        if args.output is None:
            parser.error('run requires --output')
        print(json.dumps(run(args.freeze, args.output)))


if __name__ == '__main__':
    main()
