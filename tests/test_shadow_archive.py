from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research.shadow_archive import append, initialize, main, verify

NOW = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)
LATER = datetime(2027, 11, 9, 12, tzinfo=timezone.utc)


def observation():
    return {'decision_at': '2026-11-07T11:00:00Z',
            'source': {'as_of': '2026-11-07T09:00:00Z', 'availability': 'known_publication',
                       'published_at': '2026-11-07T10:00:00Z', 'sha256': 'a'*64},
            'identity': {k+'_sha256': 'b'*64 for k in ('producer', 'config', 'readout', 'code')},
            'score': .4, 'features': {'trend': -.1}, 'forecasts': [{
                'target': 'terminal_log_return', 'horizon_months': 12,
                'atoms': [-.3, .4], 'weights': [.5, .5],
                'entry_at': '2026-11-08T00:00:00Z',
                'label_end_at': '2027-11-08T00:00:00Z', 'label_available_at': '2027-11-09T00:00:00Z'}]}


def resolution(identity):
    return {'forecast_id': identity, 'target': 'terminal_log_return', 'horizon_months': 12,
            'outcome': .2, 'source_outcome_sha256': 'c'*64,
            'source_outcome_as_of': '2027-11-08T00:00:00Z', 'provenance': 'synthetic fixture'}


class ShadowArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()/'archive'
        self.clock = patch('research.shadow_archive._now', return_value=NOW)
        self.clock.start(); self.addCleanup(self.clock.stop); self.addCleanup(self.temp.cleanup)
        initialize(self.root)

    def test_prefix_immutable_resolution_bound_and_unique(self):
        request = observation(); receipt = append(self.root, 'observation', request)
        self.assertTrue(receipt['classification']['prospective_eligibility'])
        prefix = {p.name: p.read_bytes() for p in self.root.iterdir()}
        request['forecasts'][0]['weights'] = [0., 1.]
        with patch('research.shadow_archive._now', return_value=LATER):
            resolved = append(self.root, 'resolution', resolution(receipt['event_id']))
            with self.assertRaisesRegex(ValueError, 'already resolved'):
                append(self.root, 'resolution', resolution(receipt['event_id']))
        for name, value in prefix.items(): self.assertEqual((self.root/name).read_bytes(), value)
        verified = verify(self.root, resolved['event_id'])
        self.assertEqual(verified['resolution_count'], 1)
        self.assertEqual(verified['event_count'], 2)
        self.assertEqual(json.loads(next(self.root.glob('00000001_*.json')).read_text())['request']['forecasts'][0]['weights'], [.5,.5])

    def test_prematurity_rejected_without_writing(self):
        receipt = append(self.root, 'observation', observation())
        # Endpoint exists, but publication is still one hour in the future.
        before_publication = datetime(2027, 11, 8, 23, tzinfo=timezone.utc)
        with patch('research.shadow_archive._now', return_value=before_publication):
            with self.assertRaisesRegex(ValueError, 'not yet available'):
                append(self.root, 'resolution', resolution(receipt['event_id']))
        self.assertEqual(verify(self.root)['event_count'], 1)

    def test_unknown_and_historical_never_prospective(self):
        request = observation(); request['source']['availability'] = 'unknown_vintage'
        request['source']['published_at'] = None
        receipt = append(self.root, 'observation', request)
        self.assertFalse(receipt['classification']['prospective_eligibility'])
        self.assertIn('unknown_source_vintage', receipt['classification']['reasons'])
        old = observation(); old['decision_at'] = '2026-07-30T12:00:00Z'
        old['source']['as_of'] = '2026-07-30T10:00:00Z'; old['source']['published_at'] = '2026-07-30T11:00:00Z'
        old['forecasts'][0].update(entry_at='2026-07-31T00:00:00Z', label_end_at='2027-07-31T00:00:00Z', label_available_at='2027-08-01T00:00:00Z')
        receipt = append(self.root, 'observation', old)
        self.assertEqual(receipt['classification']['reasons'], ['historical_decision_reconstruction'])
        self.assertEqual(receipt['classification']['quality_flags'], ['older_source_as_of'])

    def test_known_older_input_today_is_prospective_with_age_disclosed(self):
        request = observation()
        request['source']['as_of'] = '2026-10-07T09:00:00Z'
        # The previous-month observation was published today, before today's decision.
        receipt = append(self.root, 'observation', request)
        classification = receipt['classification']
        self.assertTrue(classification['prospective_eligibility'])
        self.assertEqual(classification['reasons'], [])
        self.assertEqual(classification['quality_flags'], ['older_source_as_of'])
        self.assertEqual(classification['source_age_seconds'], (NOW-datetime(2026,10,7,9,tzinfo=timezone.utc)).total_seconds())
        self.assertEqual(verify(self.root)['observation_count'], 1)

    def test_old_schema_is_rejected_not_reclassified(self):
        manifest_path = self.root/'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['schema'] = 'research-shadow-archive-v1'
        from research.market_dataset import canonical_bytes
        manifest_path.write_bytes(canonical_bytes(manifest))
        with self.assertRaisesRegex(ValueError, 'unsupported archive schema'):
            verify(self.root)

    def test_duplicate_decision_identity_cannot_rewrite(self):
        append(self.root, 'observation', observation())
        changed = observation(); changed['score'] = .9
        with self.assertRaisesRegex(ValueError, 'already observed'): append(self.root, 'observation', changed)
        self.assertEqual(verify(self.root)['event_count'], 1)

    def test_invalid_inputs_fail_closed(self):
        variants = []
        for field, value in [('score', float('nan')), ('observed_at', '2001-01-01T00:00:00Z'),
                             ('decision_at', '2026-11-08T00:00:00Z')]:
            row = observation(); row[field] = value; variants.append(row)
        row = observation(); row['forecasts'][0]['weights'] = [-1., 2.]; variants.append(row)
        row = observation(); row['source']['published_at'] = '2026-11-07T12:00:00Z'; variants.append(row)
        row = observation(); row['forecasts'][0]['atoms'] = [float('inf'), 1.]; variants.append(row)
        for request in variants:
            with self.assertRaises(ValueError): append(self.root, 'observation', request)
        self.assertEqual(verify(self.root)['event_count'], 0)

    def test_chain_tamper_and_trusted_head_detect_tail_deletion(self):
        receipt = append(self.root, 'observation', observation())
        path = next(self.root.glob('00000001_*.json')); original = path.read_bytes()
        event = json.loads(original); event['previous_sha256'] = '0'*64
        from research.market_dataset import canonical_bytes
        path.write_bytes(canonical_bytes(event))
        with self.assertRaisesRegex(ValueError, 'content hash mismatch'): verify(self.root)
        path.write_bytes(original); path.unlink()
        with self.assertRaisesRegex(ValueError, 'trusted head mismatch'): verify(self.root, receipt['event_id'])

    def test_concurrent_append_and_duplicate_resolution(self):
        def submit(i):
            request = observation(); request['identity']['config_sha256'] = f'{i:064x}'
            return append(self.root, 'observation', request)
        with ThreadPoolExecutor(max_workers=4) as pool:
            receipts = list(pool.map(submit, range(8)))
        self.assertEqual({r['sequence'] for r in receipts}, set(range(1,9)))
        self.assertEqual(verify(self.root)['event_count'], 8)
        def resolve(_):
            try: return append(self.root, 'resolution', resolution(receipts[0]['event_id']))
            except ValueError: return None
        with patch('research.shadow_archive._now', return_value=LATER):
            with ThreadPoolExecutor(max_workers=4) as pool: results = list(pool.map(resolve, range(4)))
        self.assertEqual(sum(r is not None for r in results), 1)
        self.assertEqual(verify(self.root)['resolution_count'], 1)

    def test_horizon_cannot_mature_early_and_calendar_matches_benchmark(self):
        from research.shadow_archive import label_calendar
        import pandas as pd
        for date, months in [('2023-01-30', 1), ('2024-01-30', 1), ('2024-02-28', 12), ('2026-11-07', 48)]:
            decision = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
            entry, end, available = label_calendar(decision, months)
            self.assertEqual(pd.Timestamp(end), pd.Timestamp(entry) + pd.DateOffset(months=months))
            self.assertEqual((available-end).days, 1)
        wrong = observation()
        wrong['forecasts'][0].update(horizon_months=48, label_end_at='2026-11-08T00:00:00Z',
                                    label_available_at='2026-11-09T00:00:00Z')
        with self.assertRaisesRegex(ValueError, 'calendar horizon'):
            append(self.root, 'observation', wrong)
        self.assertEqual(verify(self.root)['event_count'], 0)

    def test_path_loss_atoms_and_resolved_values_nonnegative(self):
        for index, target in enumerate(('entry_adverse_log_loss', 'peak_drawdown_log_loss')):
            request = observation(); request['forecasts'][0]['target'] = target
            request['identity']['config_sha256'] = f'{index:064x}'
            with self.assertRaisesRegex(ValueError, 'atoms must be nonnegative'):
                append(self.root, 'observation', request)
            request['forecasts'][0]['atoms'] = [0., .4]
            receipt = append(self.root, 'observation', request)
            outcome = resolution(receipt['event_id']); outcome.update(target=target, outcome=-.1)
            with patch('research.shadow_archive._now', return_value=LATER):
                with self.assertRaisesRegex(ValueError, 'losses must be nonnegative'):
                    append(self.root, 'resolution', outcome)
        self.assertEqual(verify(self.root)['resolution_count'], 0)

    def test_event_and_byte_caps_leave_existing_prefix_unchanged(self):
        receipt = append(self.root, 'observation', observation())
        before = verify(self.root)
        another = observation(); another['identity']['config_sha256'] = 'd'*64
        with patch('research.shadow_archive.MAX_EVENTS', 1):
            with self.assertRaisesRegex(ValueError, 'event limit reached'):
                append(self.root, 'observation', another)
        with patch('research.shadow_archive.MAX_ARCHIVE_BYTES', before['archive_bytes'] + 1):
            with self.assertRaisesRegex(ValueError, 'byte limit exceeded'):
                append(self.root, 'observation', another)
        self.assertEqual(verify(self.root, receipt['event_id']), before)

    def test_cli_synthetic_e2e_and_no_fabricated_clock(self):
        request = Path(self.temp.name)/'request.json'; request.write_text(json.dumps(observation()))
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(['observe','--archive',str(self.root),'--input',str(request)]),0)
        receipt = json.loads(output.getvalue()); self.assertEqual(receipt['observed_at'], '2026-11-07T12:00:00.000000Z')
        request.write_text(json.dumps(resolution(receipt['event_id'])))
        with patch('research.shadow_archive._now', return_value=LATER), redirect_stdout(io.StringIO()):
            self.assertEqual(main(['resolve','--archive',str(self.root),'--input',str(request)]),0)
            self.assertEqual(main(['verify','--archive',str(self.root)]),0)


if __name__ == '__main__': unittest.main()
