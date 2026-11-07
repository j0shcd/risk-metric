"""Explicit single-cohort, local noncommercial paper witness. No scheduler/trades."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research import coinmetrics_shadow as producer
from research import shadow_archive_v3 as archive
from research import shadow_capture as capture
from research.market_dataset import canonical_bytes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registration', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--live-capture', action='store_true')
    args = parser.parse_args()
    if not args.live_capture:
        parser.error('network access requires explicit --live-capture')

    registration_raw = capture.read(args.registration, archive.MAX_EVENT_BYTES)
    registration = json.loads(registration_raw)
    day = datetime.now(timezone.utc).date().isoformat()
    if day not in registration['cohort']['decision_days']:
        raise ValueError('current UTC day is not registered; never backdate or relabel')
    if registration['config'] != producer.CONFIG:
        raise ValueError('fixed paper producer configuration changed')
    if archive.source_identity(producer.produce, registration['producer']['code']) != registration['producer']:
        raise ValueError('registered producer/code/runtime drift before acquisition')

    target = capture.safe(args.output_dir).resolve()
    if not target.is_relative_to((ROOT / 'output').resolve()) or target == ROOT / 'output':
        raise ValueError('paper captures must remain in a new ignored output child')
    capture.new_directory(target)
    capture.frozen_write(target / 'requested_registration.json', registration_raw)
    capture.frozen_write(target / 'controller.py', Path(__file__).read_bytes())
    archive_root = target / 'archive'
    archive.initialize(archive_root, registration)

    try:
        observed = capture.capture_response(target / 'capture', {'query_day': day}, producer.fetch)
        issued = archive.issue(archive_root, [target / 'capture'], producer.produce)
        verified = archive.verify(archive_root, expected_head=issued['head_sha256'])
        event_path = next((archive_root / 'events').glob('*_' + issued['event_id'] + '.json'))
        event = json.loads(event_path.read_bytes())
        request = event['request']
        summary = {
            'schema': 'registered-paper-witness-v1',
            'scope': 'local noncommercial operational evidence; no model qualification or trading',
            'cohort': registration['cohort'],
            'registration_id': registration['registration_id'],
            'source': {
                'provider': 'Coin Metrics Community', 'metric': 'btc/PriceUSD/1d',
                'licence': 'https://creativecommons.org/licenses/by-nc/4.0/',
                'documentation': 'https://docs.coinmetrics.io/network-data/network-data-overview/market/price',
                'changes': 'Bar starts mapped to following UTC close; closed consecutive prices selected; registered baselines derived.',
                'capture_id': observed['capture_id'], 'raw_sha256': observed['raw_sha256'],
                'capture_started_at': observed['started_at'],
                'capture_completed_at': observed['completed_at'], 'response': observed['response'],
                'published_at': None,
            },
            'controller_sha256': capture.sha(Path(__file__).read_bytes()),
            'issue': issued, 'verification': verified,
            'selected': [{
                'closed_at': item['closed_at'], 'prefix_sha256': item['prefix_sha256'],
                'price_n': len(item['prefix']['prices']),
                'first_close_at': item['prefix']['first_close_at'],
            } for item in request['selected']],
            'forecasts': [{
                **{key: f[key] for key in (
                    'model', 'interpretation', 'target', 'horizon_months',
                    'entry_at', 'label_end_at', 'label_available_at')},
                'atom_n': len(f['atoms']),
            } for f in request['forecasts']],
            'archive_path': str(archive_root),
        }
        capture.frozen_write(target / 'witness.json', canonical_bytes(summary))
    except Exception as error:
        capture.frozen_write(target / 'run_failure.json', canonical_bytes({
            'status': 'failed_no_implicit_retry', **capture.failure_evidence(error),
        }))
        raise
    print(json.dumps({
        'status': 'paper_witness_recorded', 'cohort_kind': registration['cohort']['kind'],
        'forecast_n': len(summary['forecasts']), 'head_sha256': verified['head_sha256'],
        'metadata': str(target / 'witness.json'),
    }, sort_keys=True))


if __name__ == '__main__':
    main()
