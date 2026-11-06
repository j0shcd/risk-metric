"""Replay declared frozen candidates; never select parameters or promote a model.

CLI: python -m research.indicator_outer_replay --source FULL_SCORES.csv
     --registration REGISTRATION.json --output-dir NEW_DIRECTORY
Registration: {"source_sha256": "...", "candidates": [{"name": "...",
"column": "...", "csv": "path.csv", "csv_sha256": "...", "manifest":
"manifest.json", "manifest_sha256": "...", "provenance": "...",
"direction": "higher_risk", "frozen": true}]}. Paths resolve relative to the
registration. The declaration attests selection was frozen; the harness cannot
prove that research history. All input bytes are copied into the receipt. Pending
forecasts are reconstructions, not prospectively archived predictions.
A receipt can be replayed using its source.csv and replay_registration.json.
The module docstring owns this research-only CLI contract; promotion and shared
research status remain with the root reviewer. No production settings change.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .market_dataset import canonical_bytes, load_snapshot
from .market_information import ROLES, baseline_candidates, score_candidate
from .scorecard_artifacts import publish, safe_path, write_packet


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def checked_bytes(path, expected):
    payload = Path(path).read_bytes()
    if sha(payload) != expected:
        raise ValueError(f'input hash mismatch: {path}')
    return payload


def candidate_from_csv(payload, declaration, snapshot):
    frame = pd.read_csv(io.BytesIO(payload), index_col=0, parse_dates=True)
    required = pd.DatetimeIndex([r['date'] for r in snapshot['monthly']])
    if (frame.empty or not isinstance(frame.index, pd.DatetimeIndex)
            or frame.index.has_duplicates or not frame.index.is_monotonic_increasing
            or frame.index.tz is not None or not frame.index.equals(frame.index.normalize())
            or any(d != d + pd.offsets.MonthEnd(0) for d in frame.index)
            or declaration['column'] not in frame):
        raise ValueError('candidate requires ordered unique completed months and declared column')
    if not required.isin(frame.index).all() or any(frame.index > required[-1]):
        raise ValueError('candidate must cover full common support without future dates')
    values = frame.loc[required, declaration['column']].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError('candidate common support must be finite')
    return {'name': declaration['name'], 'direction': declaration['direction'],
            'provenance': declaration['provenance'], 'values': [
                {'date': d.date().isoformat(), 'value': float(v)} for d, v in zip(required, values)]}


def run_replay(source, registration_path):
    registration_bytes = Path(registration_path).read_bytes()
    registration = json.loads(registration_bytes)
    source_bytes = checked_bytes(source, registration['source_sha256'])
    # load_snapshot itself reads and hashes its payload. Reject a concurrent change.
    snapshot = load_snapshot(Path(source))
    if snapshot['source_sha256'] != sha(source_bytes):
        raise ValueError('source changed during loading')
    declarations = registration['candidates']
    if not isinstance(declarations, list) or not declarations:
        raise ValueError('at least one frozen candidate required')
    files = {'source.csv': source_bytes, 'registration.json': registration_bytes}
    candidates, names = [], set()
    portable = {'source_sha256': registration['source_sha256'], 'candidates': []}
    for index, declaration in enumerate(declarations):
        if declaration.get('frozen') is not True:
            raise ValueError('candidate must be declared frozen before replay')
        if (not isinstance(declaration.get('name'), str) or not declaration['name'].strip()
                or declaration['name'] in names or not isinstance(declaration.get('provenance'), str)
                or not declaration['provenance'].strip()
                or declaration.get('direction') not in ('higher_risk', 'undirected')):
            raise ValueError('candidate needs unique name, provenance and declared direction')
        names.add(declaration['name'])
        base = Path(registration_path).parent
        csv = checked_bytes(base / declaration['csv'], declaration['csv_sha256'])
        manifest = checked_bytes(base / declaration['manifest'], declaration['manifest_sha256'])
        if not isinstance(json.loads(manifest), dict):
            raise ValueError('candidate manifest must be a JSON object')
        files[f'candidate_{index}.csv'] = csv
        files[f'manifest_{index}.json'] = manifest
        portable['candidates'].append({**declaration, 'csv': f'candidate_{index}.csv',
                                       'manifest': f'manifest_{index}.json'})
        candidates.append(candidate_from_csv(csv, declaration, snapshot))
    files['replay_registration.json'] = canonical_bytes(portable)
    # All candidates are validated before any outcome scoring begins.
    results = [score_candidate(snapshot, candidate) for candidate in candidates]
    references = [score_candidate(snapshot, candidate) for candidate in baseline_candidates(snapshot)]
    for result in [*results, *references]:
        if (result['dataset_id'] != results[0]['dataset_id']
                or result['code_sha256'] != results[0]['code_sha256']):
            raise ValueError('candidate/reference benchmark identity mismatch')
    replay = {'status': 'frozen_pseudo_out_of_sample_reconstruction_no_promotion',
              'source_sha256': sha(source_bytes), 'registration_sha256': sha(registration_bytes),
              'harness_sha256': sha(Path(__file__).read_bytes()), 'results': results,
              'references': references, 'selection': 'none; all declared candidates retained'}
    return replay, files


def readable(replay):
    lines = ['# Frozen indicator replay', '',
             'Chronological pseudo-out-of-sample reconstruction, not an unseen holdout or prospective forecast.',
             'No selection, combined objective, market significance or production promotion. Lower CRPS is better.',
             'Best reference is a descriptive per-cell comparison, not a selected forecasting model.', '']
    for result in replay['results']:
        lines += [f"## {result['candidate_name']}", '',
                  '| Role | Months | Outcome | Forecast / scored n | Candidate | Context | Unconditional | Best fixed reference | Ordering |',
                  '|---|---:|---|---:|---:|---:|---:|---|---:|']
        for role in ROLES:
            for cell in (c for c in result['cells'] if c['role'] == role):
                refs = [(r['candidate_name'], c['candidate_mean_crps']) for r in replay['references'] for c in r['cells']
                        if (c['role'], c['horizon'], c['target'], c['scored_origins_id']) ==
                        (role, cell['horizon'], cell['target'], cell['scored_origins_id'])
                        and c['candidate_mean_crps'] is not None]
                best = min(refs, key=lambda pair: pair[1]) if refs else None
                def show(value): return '—' if value is None else f'{value:.6f}'
                label = '—' if best is None else f'{best[0]} ({best[1]:.6f})'
                lines.append(f"| {role} | {cell['horizon']} | {cell['target']} | {cell['forecast_n']} / {cell['scored_n']} | {show(cell['candidate_mean_crps'])} | {show(cell['reference_mean_crps'])} | {show(cell['unconditional_mean_crps'])} | {label} | {show(cell['ordinal_alignment'])} |")
        lines += ['', *[f'- {note}' for note in result['limitations']], '']
    return ('\n'.join(lines) + '\n').encode()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--registration', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    target = safe_path(args.output_dir)
    target.mkdir(exist_ok=False)
    publish(target/'request.json', canonical_bytes({'source': str(args.source), 'registration': str(args.registration)}))
    try:
        replay, files = run_replay(args.source, args.registration)
    except (ValueError, KeyError, TypeError, OSError) as error:
        write_packet(target, {'error.json': canonical_bytes({'status': 'ineligible', 'reason': str(error)})}, bound_existing=('request.json',))
        raise
    write_packet(target, {**files, 'replay.json': canonical_bytes(replay), 'report.md': readable(replay)}, bound_existing=('request.json',))
    print(json.dumps({'status': replay['status'], 'report': str(target/'report.md')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
