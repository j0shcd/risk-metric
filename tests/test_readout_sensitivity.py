"""Boundary checks for the registered audit, using separate engineering worlds."""
import ast
import copy
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from research import readout_sensitivity as audit
from research import readout_synthetic_world as law
from research.distribution_readout import mixture_forecasts
from research.market_dataset import TARGETS, build_dataset
from research.market_information import score_candidate


class SensitivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = law.make_world(7, .15, root_seed=law.ENGINEERING_SEED)
        cls.packet = audit.audit_world(7, .15, root_seed=law.ENGINEERING_SEED, paths=4)

    def test_frozen_caller_parity_and_independent_training_inventory(self):
        scored = score_candidate(self.world['snapshot'], audit.candidate(self.world, 'noisy'))
        rows = build_dataset(self.world['snapshot'], [12, 24, 48])['rows']
        by_date = {row['date']: row for row in rows}
        by_record = {(r['date'], r['horizon'], r['target']): r for r in scored['predictions']}
        self.assertEqual(len(self.packet['records']), 216)
        for record in self.packet['records']:
            date, horizon = record['date'], record['horizon']
            eligible = [row['date'] for row in rows if row['date'] < date and row['context'] is not None
                        and row['outcomes'][str(horizon)]['status'] == 'complete'
                        and row['outcomes'][str(horizon)]['available'] < date][-24:]
            self.assertEqual(record['train_dates'], eligible)
            direct = by_record[(date, horizon, record['target'])]
            self.assertEqual(record['arms']['noisy']['weights'], direct['candidate_weights'])
            self.assertEqual(record['metrics']['noisy']['crps'], direct['candidate_crps'])
            for training in eligible:
                self.assertLess(by_date[training]['outcomes'][str(horizon)]['available'], date)

    def test_score_arithmetic_independently_from_retained_atoms(self):
        for row in self.packet['records']:
            atoms = np.array(row['atoms'])
            observed = row['outcome']
            for arm in audit.ARMS:
                weights = np.array(row['arms'][arm]['weights'])
                loss = weights @ abs(atoms-observed) - .5*(weights[:, None]*weights*abs(atoms[:, None]-atoms)).sum()
                self.assertAlmostEqual(row['metrics'][arm]['crps'], loss, places=13)
                event = observed < 0 if row['target'] == TARGETS[0] else observed > math.log(2)
                mask = atoms < 0 if row['target'] == TARGETS[0] else atoms > math.log(2)
                self.assertAlmostEqual(row['metrics'][arm]['brier'], (weights @ mask-event)**2)
            self.assertEqual(row['metrics']['constant'], row['metrics']['reference'])

    def test_suffix_does_not_change_earlier_issued_distributions(self):
        before = score_candidate(self.world['snapshot'], audit.candidate(self.world, 'exact'))
        revised = copy.deepcopy(self.world)
        for row in revised['snapshot']['daily']:
            if row['date'] > '2019-12-31':
                row['price'] *= 5
        # Feature archive itself may have arbitrary later suffix revisions too.
        revised['features']['exact'][61:] += 200
        after = score_candidate(revised['snapshot'], audit.candidate(revised, 'exact'))
        left = [r for r in before['predictions'] if r['date'] <= '2019-12-31']
        right = [r for r in after['predictions'] if r['date'] <= '2019-12-31']
        for a, b in zip(left, right, strict=True):
            for field in ('date', 'horizon', 'atoms', 'train_dates', 'thresholds', 'reference_weights', 'candidate_weights'):
                self.assertEqual(a[field], b[field])

    def test_constant_duplicate_context_and_empty_cell_identities(self):
        context = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], float)
        for column in (np.zeros(4), context[:, 0]):
            features = np.column_stack((context, column))
            result = mixture_forecasts(features, features, features[0])
            np.testing.assert_array_equal(result['reference'], result['candidate'])
        features = np.column_stack((np.zeros((4, 2)), np.zeros(4)))
        result = mixture_forecasts(features, features, np.array([0., 0., 1.]))
        self.assertTrue(result['candidate_fallback'])
        np.testing.assert_array_equal(result['reference'], result['candidate'])

    def test_local_imports_are_bound_by_scoring_freeze(self):
        bound = set(audit.implementation()) | {'research/'+name for name in audit.registration()['frozen_code_sha256']}
        for source in ('research/readout_sensitivity.py', 'research/readout_synthetic_world.py'):
            tree = ast.parse((audit.root_path()/source).read_text())
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level == 1:
                    imports.extend([node.module] if node.module else [a.name for a in node.names])
            for name in imports:
                self.assertIn('research/'+name+'.py', bound, f'unbound scoring import in {source}')

    def test_registration_and_freeze_fail_closed(self):
        self.assertEqual(audit.registration()['budget']['decoder_calls'], 512)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'freeze.json'
            audit.freeze(path)
            audit.verify_freeze(path)
            with self.assertRaises(FileExistsError):
                audit.freeze(path)
            with patch.object(audit, 'runtime', return_value={'wrong': 'runtime'}):
                with self.assertRaisesRegex(ValueError, 'changed after freeze'):
                    audit.verify_freeze(path)
            with patch.object(audit, 'implementation', return_value={'wrong': 'code'}):
                with self.assertRaisesRegex(ValueError, 'changed after freeze'):
                    audit.verify_freeze(path)

    def test_whole_world_aggregation_and_unavailable_horizon(self):
        worlds = []
        # A different origin count would change a row-weighted estimate. The
        # boundary rejects that rather than silently reducing denominators.
        for i in range(3):
            w = copy.deepcopy(self.packet)
            w['world_id'] = i
            for row in w['records']:
                for model, metrics in row['metrics'].items():
                    metrics['crps'] = float(i+1) + (10 if model == 'reference' else 0)
            worlds.append(w)
        result = audit.summarize(worlds, 100, 93117)
        primary = next(c for c in result['cells'] if c['horizon'] == 24 and c['target'] == TARGETS[0])
        contrast = primary['contrasts']['exact']['reference_minus_candidate']['crps']
        self.assertEqual(contrast['world_n'], 3)
        self.assertEqual(contrast['mean'], 10.)
        self.assertEqual(contrast['pointwise_95_percentile_world_bootstrap'], [10., 10.])
        self.assertTrue(all(c['status'] == 'unavailable_by_registered_calendar' for c in result['cells'] if c['horizon'] == 48))
        worlds[0]['records'].pop()
        with self.assertRaisesRegex(ValueError, 'unequal world support'):
            audit.summarize(worlds, 10, 93117)


if __name__ == '__main__':
    unittest.main()
