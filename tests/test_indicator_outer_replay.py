from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from research.indicator_outer_replay import main, run_replay
from research.market_dataset import load_snapshot
from research.scorecard_artifacts import verify_packet
from tests.test_market_scorecard import snapshot, write_source


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class OuterReplayTests(unittest.TestCase):
    def fixture(self, root):
        # Synthetic random walk only; shift fixture dates across the fixed role boundary.
        synthetic = snapshot(110)
        for rows in (synthetic['daily'], synthetic['monthly']):
            for row in rows:
                row['date'] = (pd.Timestamp(row['date']) + pd.DateOffset(years=16)).date().isoformat()
        source = root/'source.csv'
        write_source(source, synthetic)
        data = load_snapshot(source)
        csv = root/'signal.csv'
        pd.DataFrame({'Date': [r['date'] for r in data['monthly']],
                      'signal': [r['dca_risk'] for r in data['monthly']]}).to_csv(csv, index=False)
        manifest = root/'manifest.json'
        manifest.write_text(json.dumps({'candidate': 'synthetic_incumbent', 'fixed_parameters': {}}))
        registration = {'source_sha256': sha(source), 'candidates': [{
            'name': 'synthetic_incumbent', 'column': 'signal', 'csv': csv.name,
            'csv_sha256': sha(csv), 'manifest': manifest.name, 'manifest_sha256': sha(manifest),
            'provenance': 'synthetic fixture only', 'direction': 'higher_risk', 'frozen': True}]}
        path = root/'registration.json'
        path.write_text(json.dumps(registration))
        return source, path, registration

    def test_all_roles_and_fixed_references_remain_separate(self):
        with tempfile.TemporaryDirectory() as raw:
            source, path, registration = self.fixture(Path(raw))
            second = {**registration['candidates'][0], 'name': 'second_frozen_declaration'}
            registration['candidates'].append(second)
            path.write_text(json.dumps(registration))
            replay, files = run_replay(source, path)
            self.assertEqual([r['candidate_name'] for r in replay['results']],
                             ['synthetic_incumbent', 'second_frozen_declaration'])
            self.assertEqual(len(replay['references']), 13)
            result = replay['results'][0]
            self.assertEqual({c['role'] for c in result['cells']},
                             {'development', 'outer', 'retrospective_challenge', 'pending', 'outcome_unavailable'})
            self.assertTrue(any(c['scored_n'] for c in result['cells'] if c['role'] == 'outer'))
            self.assertTrue(any(c['scored_n'] for c in result['cells'] if c['role'] == 'retrospective_challenge'))
            self.assertTrue(any(c['scored_n'] for c in result['cells'] if c['role'] == 'development'))
            incumbent = next(r for r in replay['references'] if r['candidate_name'] == 'dca_risk')
            for cell, ref in zip(result['cells'], incumbent['cells']):
                self.assertEqual(cell['candidate_mean_crps'], ref['candidate_mean_crps'])
                self.assertEqual(cell['unconditional_mean_crps'], ref['unconditional_mean_crps'])
                if cell['role'] == 'pending':
                    self.assertEqual(cell['scored_n'], 0)
                    self.assertIsNone(cell['candidate_mean_crps'])
            self.assertEqual(files['source.csv'], source.read_bytes())
            self.assertIn('manifest_0.json', files)
            self.assertEqual(result['minimum_training'], 24)
            self.assertEqual({c['horizon'] for c in result['cells']}, {12, 24, 48})

    def test_hash_mismatch_fails_before_scoring(self):
        with tempfile.TemporaryDirectory() as raw:
            source, path, registration = self.fixture(Path(raw))
            for field in ('source_sha256', 'csv_sha256', 'manifest_sha256'):
                changed = deepcopy(registration)
                owner = changed if field == 'source_sha256' else changed['candidates'][0]
                owner[field] = 'bad'
                path.write_text(json.dumps(changed))
                with patch('research.indicator_outer_replay.score_candidate') as score:
                    with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                        run_replay(source, path)
                    score.assert_not_called()

    def test_missing_nonfinite_future_dates_and_unfrozen_fail_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source, path, registration = self.fixture(root)
            csv = root/'signal.csv'
            original = pd.read_csv(csv)
            variants = [original.iloc[1:].copy(), original.copy(), original.copy()]
            variants[1].loc[0, 'signal'] = float('nan')
            variants[2].loc[len(original)] = ['2030-01-31', .5]
            for frame in variants:
                frame.to_csv(csv, index=False)
                registration['candidates'][0]['csv_sha256'] = sha(csv)
                path.write_text(json.dumps(registration))
                with patch('research.indicator_outer_replay.score_candidate') as score:
                    with self.assertRaises(ValueError): run_replay(source, path)
                    score.assert_not_called()
            registration['candidates'][0]['frozen'] = False
            path.write_text(json.dumps(registration))
            with self.assertRaisesRegex(ValueError, 'declared frozen'): run_replay(source, path)

    def test_exclusive_portable_receipt_includes_every_input(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            source, registration, _ = self.fixture(root)
            target = root/'replay'
            args = ['--source', str(source), '--registration', str(registration), '--output-dir', str(target)]
            with redirect_stdout(io.StringIO()): self.assertEqual(main(args), 0)
            receipt = verify_packet(target)
            self.assertTrue({'source.csv', 'registration.json', 'candidate_0.csv', 'manifest_0.json',
                             'replay.json', 'report.md'}.issubset(receipt['files']))
            report = (target/'report.md').read_text()
            for role in ('development', 'outer', 'retrospective_challenge', 'pending'):
                self.assertIn(f'| {role} |', report)
            rerun, _ = run_replay(target/'source.csv', target/'replay_registration.json')
            original = json.loads((target/'replay.json').read_text())
            self.assertEqual(rerun['results'], original['results'])
            with self.assertRaises(FileExistsError): main(args)


if __name__ == '__main__':
    unittest.main()
