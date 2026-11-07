"""Version 2: exact rank-coordinate equivalence, development-only decoder study.

Reuses the frozen v1 evaluator under a scoped decoder injection. This wrapper is
single-threaded: do not call it concurrently with v1 in the same interpreter.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
from . import readout_study as v1
from .market_dataset import canonical_bytes, load_snapshot
from .market_information import baseline_candidates
from .scorecard_artifacts import publish, safe_path, write_packet

ORIGINAL_DECODE = v1.decode
PROTOCOL = {**v1.PROTOCOL, 'version': 'rank-equivalence-v2',
            'rank_equivalence': 'exact training rank vector AND query rank; one equally weighted canonical coordinate per class',
            'trial_accounting': 'additional decoded-representation study after inspecting v1; not a new candidate or independent validation'}

def canonical_rank_coordinates(ranks, query):
    """Collapse exact equal coordinates including query; sorted for permutation invariance."""
    coordinates = np.column_stack([np.asarray(ranks, float).T, np.asarray(query, float)])
    unique = np.unique(coordinates, axis=0)
    return unique[:, :-1].T, unique[:, -1]

def decode(train, query, method, fallback=None):
    if method != 'rank':
        return ORIGINAL_DECODE(train, query, method, fallback)
    train, query = np.asarray(train, float), np.asarray(query, float)
    if (train.ndim != 2 or len(train) != 24 or train.shape[1] < 1 or query.shape != (train.shape[1],)
            or not np.isfinite(train).all() or not np.isfinite(query).all()):
        raise ValueError('Require 24 finite training rows and a finite matching query')
    ranks, q = v1.percentile(train, query)
    ranks, q = canonical_rank_coordinates(ranks, q)
    distance = np.abs(ranks-q).mean(axis=1)
    boundary = np.sort(distance)[7]
    ties = np.isclose(distance, boundary, rtol=0, atol=1e-12)
    inside = (distance < boundary) & ~ties
    membership = inside.astype(float) + ties * ((8-int(inside.sum())) / int(ties.sum()))
    weights = .5 * np.full(24, 1/24) + .5 * membership / 8
    return weights, {'fallback': False, 'local_mass': float(membership.sum()),
                     'local_nonzero_n': int((membership > 0).sum()),
                     'weight_concentration_n': float(1 / np.square(weights).sum()),
                     'rank_coordinate_classes': int(ranks.shape[1])}

def evaluate(snapshot, candidates):
    with patch.object(v1, 'decode', decode):
        result = v1.evaluate(snapshot, candidates)
    result['protocol'] = PROTOCOL
    result['limitations'].append('Exact coordinate duplication is removed; general nonlinear redundancy and restricted decoder capacity remain.')
    return result

def run(bundle, output):
    manifest = json.loads((bundle/'manifest.json').read_text())
    if manifest['cutoff'] != v1.CUTOFF:
        raise ValueError('Wrong development cutoff')
    for name in ['development_scores.csv', 'btc_daily.csv']:
        if hashlib.sha256((bundle/name).read_bytes()).hexdigest() != manifest['sources'][name]['development_sha256']:
            raise ValueError('Input hash mismatch')
    snapshot = load_snapshot(bundle/'development_scores.csv')
    raw = pd.read_csv(bundle/'btc_daily.csv')
    if pd.to_datetime(raw.Date).max() > pd.Timestamp(v1.CUTOFF):
        raise ValueError('Future prices prohibited')
    from .candidates.swing_b.generator import generate
    fixed = generate(raw)['swing_b_adaptive']
    candidates = baseline_candidates(snapshot)
    candidates.append({'name': 'swing_b_adaptive', 'direction': 'higher_risk', 'provenance': 'frozen8837516',
                       'values': [{'date': r['date'], 'value': float(fixed.loc[r['date']])} for r in snapshot['monthly']]})
    result = evaluate(snapshot, candidates)
    result['source_hashes'] = {name: hashlib.sha256((bundle/name).read_bytes()).hexdigest()
                               for name in ['manifest.json', 'development_scores.csv', 'btc_daily.csv']}
    result['code_hashes'] = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                             for name in ['readout_study_v2.py', 'readout_study.py', 'market_dataset.py',
                                          'market_information.py', 'market_scorecard.py', 'distribution_readout.py']}
    result['generator_sha256'] = hashlib.sha256(Path(__file__).parent.joinpath('candidates/swing_b/generator.py').read_bytes()).hexdigest()
    write_packet(output, {'study.json': canonical_bytes(result)}, bound_existing=('request.json',))
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    output = safe_path(args.output_dir)
    output.mkdir(exist_ok=False)
    publish(output/'request.json', canonical_bytes({'bundle': str(args.bundle), 'protocol': PROTOCOL}))
    try:
        result = run(args.bundle, output)
    except Exception as error:
        publish(output/'error.json', canonical_bytes({'error': str(error)}))
        raise
    print(json.dumps({'output': str(output), 'cells': len(result['cells']),
                      'support': {k: len(v) for k,v in result['support'].items()}}))

if __name__ == '__main__':
    main()
