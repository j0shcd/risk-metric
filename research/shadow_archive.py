"""Local append-only research observations; no scheduler, network or promotion.

CLI: python -m research.shadow_archive init|observe|resolve|verify --archive DIR
Observe/resolve require --input JSON. Verify optionally accepts --expected-head
from an independently retained receipt. Runtime UTC time cannot be supplied by CLI.
A local chain detects corruption; trusted external heads are needed to detect
adversarial tail deletion or a complete rewrite. Hashes identify, not authenticate,
source/producers. Publication claims must be verified by the caller.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
from pathlib import Path
import re

from .market_dataset import canonical_bytes, TARGETS
from .scorecard_artifacts import publish, safe_path

SCHEMA = 'research-shadow-archive-v1'


def _now():
    return datetime.now(timezone.utc)


def _stamp(value):
    return value.isoformat(timespec='microseconds').replace('+00:00', 'Z')


def _time(value):
    if not isinstance(value, str):
        raise ValueError('timestamp must be an explicit UTC ISO string')
    try:
        date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as error:
        raise ValueError('invalid UTC timestamp') from error
    if date.tzinfo is None or date.utcoffset().total_seconds() != 0:
        raise ValueError('timestamp must be UTC')
    return date


def _hash(payload):
    return hashlib.sha256(payload).hexdigest()


def _sha(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('expected lowercase SHA256')


def _keys(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError('unexpected or missing request fields')


def _finite(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('values must be finite numbers')


def _positive_int(value):
    if type(value) is not int or value < 1:
        raise ValueError('horizon must be a positive integer')


def _validate_observation(request, now):
    _keys(request, ('decision_at', 'source', 'identity', 'score', 'features', 'forecasts'))
    decision = _time(request['decision_at'])
    if decision > now:
        raise ValueError('decision cannot follow actual observation time')
    source = request['source']
    _keys(source, ('as_of', 'availability', 'published_at', 'sha256'))
    _sha(source['sha256'])
    as_of = _time(source['as_of'])
    if as_of > decision:
        raise ValueError('source as_of cannot follow decision')
    reasons = []
    if source['availability'] == 'known_publication':
        published = _time(source['published_at'])
        if not as_of <= published <= decision:
            raise ValueError('known source publication must lie between as_of and decision')
    elif source['availability'] == 'unknown_vintage' and source['published_at'] is None:
        reasons.append('unknown_source_vintage')
    else:
        raise ValueError('availability must explicitly declare known publication or unknown vintage')
    if decision.date() != now.date():
        reasons.append('historical_decision_reconstruction')
    if as_of.date() != now.date():
        reasons.append('stale_source_as_of')
    identity = request['identity']
    _keys(identity, ('config_sha256', 'producer_sha256', 'readout_sha256', 'code_sha256'))
    for value in identity.values(): _sha(value)
    _finite(request['score'])
    if not isinstance(request['features'], dict) or not request['features']:
        raise ValueError('nonempty features required')
    for name, value in request['features'].items():
        if not isinstance(name, str) or not name.strip(): raise ValueError('feature name required')
        _finite(value)
    forecasts = request['forecasts']
    if not isinstance(forecasts, list) or not forecasts:
        raise ValueError('nonempty forecasts required')
    seen = set()
    for forecast in forecasts:
        _keys(forecast, ('target', 'horizon_months', 'atoms', 'weights', 'label_end_at', 'label_available_at'))
        _positive_int(forecast['horizon_months'])
        key = (forecast['target'], forecast['horizon_months'])
        if forecast['target'] not in TARGETS or key in seen:
            raise ValueError('forecast target/horizon must be supported and unique')
        seen.add(key)
        end, available = _time(forecast['label_end_at']), _time(forecast['label_available_at'])
        if not decision < end <= available:
            raise ValueError('label end/availability must follow decision in order')
        if available <= now and 'already_mature_at_observation' not in reasons:
            reasons.append('already_mature_at_observation')
        if end <= now and 'outcome_endpoint_already_observed' not in reasons:
            reasons.append('outcome_endpoint_already_observed')
        atoms, weights = forecast['atoms'], forecast['weights']
        if not isinstance(atoms, list) or not isinstance(weights, list) or not atoms or len(atoms) != len(weights):
            raise ValueError('nonempty equal-sized atom/weight vectors required')
        for value in atoms + weights: _finite(value)
        if min(weights) < 0 or not math.isclose(sum(weights), 1., rel_tol=0., abs_tol=1e-12):
            raise ValueError('weights must be nonnegative and sum to one')
    return {'prospective_eligibility': not reasons,
            'classification': 'prospective_eligible_observation' if not reasons else 'retrospective_or_unverified_observation',
            'reasons': reasons}


def _ensure_new_observation(request, observations):
    if any(_time(old['decision_at']) == _time(request['decision_at']) and old['identity'] == request['identity']
           for old in observations.values()):
        raise ValueError('decision/producer identity already observed; use a new decision or model identity')


def _validate_resolution(request, now, observations, resolutions):
    _keys(request, ('forecast_id', 'target', 'horizon_months', 'outcome',
                    'source_outcome_sha256', 'source_outcome_as_of', 'provenance'))
    _sha(request['forecast_id']); _sha(request['source_outcome_sha256'])
    _positive_int(request['horizon_months']); _finite(request['outcome'])
    if not isinstance(request['provenance'], str) or not request['provenance'].strip():
        raise ValueError('outcome provenance required')
    key = (request['forecast_id'], request['target'], request['horizon_months'])
    if key in resolutions:
        raise ValueError('outcome already resolved; prior labels are immutable')
    observation = observations.get(request['forecast_id'])
    if observation is None: raise ValueError('unknown forecast identity')
    forecast = next((f for f in observation['forecasts'] if
                     (f['target'], f['horizon_months']) == key[1:]), None)
    if forecast is None: raise ValueError('unknown target/horizon')
    if now < _time(forecast['label_available_at']):
        raise ValueError('outcome label is not yet available')
    if not _time(forecast['label_end_at']) <= _time(request['source_outcome_as_of']) <= now:
        raise ValueError('outcome source must cover endpoint and cannot be from the future')
    return key


@contextmanager
def _lock(root, exclusive=True):
    root = safe_path(Path(root))
    # The lock inode is created only by init and is never replaced or truncated.
    with safe_path(root/'archive.lock').open('r') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try: yield root
        finally: fcntl.flock(lock, fcntl.LOCK_UN)


def initialize(root):
    root = safe_path(Path(root)); root.mkdir(exist_ok=False)
    publish(root/'archive.lock', b'')
    with _lock(root):
        manifest = {'schema': SCHEMA, 'created_at': _stamp(_now()),
                    'archive_code_sha256': _hash(Path(__file__).read_bytes())}
        publish(root/'manifest.json', canonical_bytes(manifest))
    return verify(root)


def _read(root, expected_head=None):
    manifest_bytes = safe_path(root/'manifest.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    _keys(manifest, ('schema', 'created_at', 'archive_code_sha256'))
    if manifest['schema'] != SCHEMA: raise ValueError('unsupported archive schema')
    _sha(manifest['archive_code_sha256']); previous_time = _time(manifest['created_at'])
    head = _hash(manifest_bytes); observations, resolutions = {}, set()
    names = sorted(p.name for p in root.iterdir() if p.name not in ('manifest.json', 'archive.lock'))
    for sequence, name in enumerate(names, 1):
        if not re.fullmatch(rf'{sequence:08d}_[0-9a-f]{{64}}\.json', name):
            raise ValueError('event sequence gap or unexpected file')
        payload = safe_path(root/name).read_bytes()
        if name != f'{sequence:08d}_{_hash(payload)}.json': raise ValueError('event content hash mismatch')
        event = json.loads(payload)
        _keys(event, ('sequence', 'previous_sha256', 'observed_at', 'kind', 'request', 'classification', 'archive_code_sha256'))
        if type(event['sequence']) is not int or event['sequence'] != sequence or event['previous_sha256'] != head:
            raise ValueError('event chain mismatch')
        if payload != canonical_bytes(event): raise ValueError('noncanonical event')
        _sha(event['archive_code_sha256']); now = _time(event['observed_at'])
        if now < previous_time: raise ValueError('observation clock moved backwards')
        event_hash = _hash(payload)
        if event['kind'] == 'observation':
            classification = _validate_observation(event['request'], now)
            _ensure_new_observation(event['request'], observations)
            if event['classification'] != classification: raise ValueError('eligibility classification mismatch')
            observations[event_hash] = event['request']
        elif event['kind'] == 'resolution':
            if event['classification'] is not None: raise ValueError('unexpected resolution classification')
            resolutions.add(_validate_resolution(event['request'], now, observations, resolutions))
        else: raise ValueError('unsupported event kind')
        head, previous_time = event_hash, now
    if expected_head is not None and head != expected_head: raise ValueError('trusted head mismatch')
    return {'head_sha256': head, 'event_count': len(names), 'observation_count': len(observations),
            'resolution_count': len(resolutions)}, observations, resolutions, previous_time


def verify(root, expected_head=None):
    with _lock(root, False) as root:
        return _read(root, expected_head)[0]


def append(root, kind, request):
    # Round-trip rejects non-JSON/nonfinite values and isolates caller mutation.
    request = json.loads(canonical_bytes(request))
    with _lock(root) as root:
        receipt, observations, resolutions, previous_time = _read(root)
        now = _now()
        if now < previous_time: raise ValueError('observation clock moved backwards')
        if kind == 'observation':
            classification = _validate_observation(request, now)
            _ensure_new_observation(request, observations)
        elif kind == 'resolution':
            _validate_resolution(request, now, observations, resolutions); classification = None
        else: raise ValueError('unsupported event kind')
        event = {'sequence': receipt['event_count'] + 1, 'previous_sha256': receipt['head_sha256'],
                 'observed_at': _stamp(now), 'kind': kind, 'request': request, 'classification': classification,
                 'archive_code_sha256': _hash(Path(__file__).read_bytes())}
        payload = canonical_bytes(event)
        publish(root/f"{event['sequence']:08d}_{_hash(payload)}.json", payload)
        return {'event_id': _hash(payload), 'sequence': event['sequence'], 'observed_at': event['observed_at'],
                'classification': classification, 'previous_sha256': receipt['head_sha256']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('init', 'observe', 'resolve', 'verify'))
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--expected-head')
    args = parser.parse_args(argv)
    if args.operation in ('observe', 'resolve'):
        if args.input is None or args.expected_head is not None: parser.error('observe/resolve require --input only')
        result = append(args.archive, 'observation' if args.operation == 'observe' else 'resolution', json.loads(args.input.read_bytes()))
    elif args.operation == 'init':
        if args.input is not None or args.expected_head is not None: parser.error('init takes no input/head')
        result = initialize(args.archive)
    else:
        if args.input is not None: parser.error('verify takes no input')
        result = verify(args.archive, args.expected_head)
    print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
