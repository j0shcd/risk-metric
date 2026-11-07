"""Deterministic synthetic adapters only; no market fit or model selection."""
from copy import deepcopy
from dataclasses import dataclass
from itertools import product
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
import tempfile
import io
import json
import types
import unittest
import numpy as np
import pandas as pd

from research.generative_forecast_scorecard import (
    PROTOCOL, distribution_summary, evaluate, simulation_seed, main, sha, code_identity, runtime_identity,
)
from research.market_dataset import COMPONENTS, digest, load_snapshot, canonical_bytes
from research.scorecard_artifacts import verify_packet
from tests.test_market_scorecard import write_source
from research.market_information import baseline_candidates, score_candidate


@dataclass
class ToyPosterior:
    mean: float
    diagnostics: dict


class ToyModel:
    PROTOCOL = {'name':'synthetic-test-adapter', 'paths':16}
    def __init__(self): self.fit_inputs=[]; self.simulation_calls=[]
    def fit(self, returns):
        self.fit_inputs.append(returns.copy())
        return ToyPosterior(float(np.mean(returns)), {'fit_n':len(returns)})
    def simulate(self, posterior, holding_days, *, seed):
        self.simulation_calls.append((tuple(holding_days),seed))
        # Toy target vectors, deliberately not a statistical price-model substitute.
        z=np.random.default_rng(seed).normal(size=16)
        return np.stack([np.column_stack([posterior.mean*d+z*.01*np.sqrt(d),
                                         abs(z)*.01*np.sqrt(d), abs(z)*.02*np.sqrt(d)])
                         for d in holding_days],axis=1)


def fixture(end='2025-03-01'):
    dates=pd.date_range('2016-01-01',end,freq='D'); t=np.arange(len(dates))
    prices=np.exp(4+.0002*t+.15*np.sin(t/90))
    monthly=pd.date_range('2017-01-31',dates[-1],freq='ME')
    snapshot={'daily':[{'date':d.date().isoformat(),'price':float(p)} for d,p in zip(dates,prices)],
              'monthly':[{'date':d.date().isoformat(),**{c:.5 for c in COMPONENTS}} for d in monthly]}
    snapshot['source_sha256']=digest(snapshot['daily'])
    return snapshot


def references(snapshot):
    return [score_candidate(snapshot,baseline_candidates(snapshot)[0])]


def registration():
    return {'protocol':PROTOCOL,'ensemble_interpretation':'iid_predictive_law_draws','replica_seeds':[15001,25001],'sample_count':16,
            'model_protocol':ToyModel.PROTOCOL, 'runtime':runtime_identity(), 'scorecard_code_sha256':code_identity()}


class GenerativeScorecardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot=fixture(); cls.references=references(cls.snapshot)

    def test_price_only_support_strict_history_calendar_and_roles(self):
        model=ToyModel(); report=evaluate(self.snapshot,self.references,model,registration())
        eligible=[r for r in report['eligibility'] if r['eligible']]
        self.assertEqual(len(model.fit_inputs),len(eligible))
        self.assertEqual(len(model.simulation_calls),2*len(eligible))
        dates=pd.DatetimeIndex([r['date'] for r in self.snapshot['daily']])
        prices=np.array([r['price'] for r in self.snapshot['daily']])
        for row,returns in zip(eligible,model.fit_inputs):
            i=dates.get_loc(row['date'])
            np.testing.assert_array_equal(returns,np.diff(np.log(prices[i-730:i+1])))
            self.assertEqual(len(returns),730)
        self.assertLess(eligible[0]['date'],min(r['date'] for r in self.references[0]['predictions']))
        for record in report['records']:
            if record['model']!='generative':continue
            entry=pd.Timestamp(record['date'])+pd.Timedelta(days=1)
            end=entry+pd.DateOffset(months=record['horizon'])
            self.assertEqual(record['holding_days'],(end-entry).days)
            self.assertEqual(record['label_available'],(end+pd.Timedelta(days=1)).date().isoformat())
            if record['role']=='pending':self.assertNotIn('crps',record)
            self.assertNotIn('atoms',record)
        self.assertTrue({'development','outer','retrospective_challenge','pending'}.issubset(
            {r['role'] for r in report['records']}))
        cells=report['cells']
        for cell in cells:
            if cell['model']=='generative' and cell['support']=='matched_direct_cdf':
                ref=next(c for c in cells if c['model']=='unconditional' and
                         (c['role'],c['horizon'],c['target'])==(cell['role'],cell['horizon'],cell['target']))
                self.assertEqual(cell['origins_id'],ref['origins_id'])
                self.assertEqual(cell['requested_n'],ref['requested_n'])
        self.assertFalse(any(c['model']!='generative' and c['support']=='all_generative_eligible' for c in cells))

    def test_future_suffix_and_earlier_support_do_not_change_simulation(self):
        short=fixture('2024-03-01'); full=deepcopy(self.snapshot)
        for row in full['daily']:
            if row['date']>'2024-03-01': row['price']*=100
        full['source_sha256']=digest(full['daily'])
        # Earlier incumbent support changes the reference dataset, never simulation seeds.
        earlier=pd.date_range('2016-01-31','2016-12-31',freq='ME')
        full['monthly']=[{'date':d.date().isoformat(),**{c:.5 for c in COMPONENTS}} for d in earlier]+full['monthly']
        a=evaluate(short,references(short),ToyModel(),registration())
        b=evaluate(full,references(full),ToyModel(),registration())
        bfits={r['date']:r for r in b['fits']}
        for fit in a['fits']:self.assertEqual(fit,bfits[fit['date']])
        bykey={(r['date'],r['horizon'],r['target'],r['replica']):r for r in b['records'] if r['model']=='generative'}
        for record in (r for r in a['records'] if r['model']=='generative'):
            other=bykey[(record['date'],record['horizon'],record['target'],record['replica'])]
            for name in ('seed','fit_id','atoms_identity','intervals','event_probability'):
                self.assertEqual(record[name],other[name])
        self.assertEqual(simulation_seed(15001,'2020-01-31'),simulation_seed(15001,'2020-01-31'))
        self.assertNotEqual(simulation_seed(15001,'2020-01-31'),simulation_seed(25001,'2020-01-31'))

    def test_nested_horizon_provider_boundary_and_metric_definition(self):
        model=ToyModel(); fit=model.fit(np.zeros(730))
        np.testing.assert_array_equal(model.simulate(fit,[365,730],seed=1),
                                      model.simulate(fit,[365,730,1461],seed=1)[:,:2])
        atoms=np.array([-1.,0.,1.,2.]);weights=np.full(4,.25);observed=.5
        result=distribution_summary(atoms,weights,'terminal_log_return',observed)
        expected=np.mean(abs(atoms-observed))-.5*np.mean(abs(atoms[:,None]-atoms[None,:]))
        self.assertAlmostEqual(result['crps'],expected)
        self.assertEqual(result['event_probability'],.25)
        self.assertEqual(result['brier'],.25**2)
        self.assertEqual(result['intervals']['50'],[-1.,1.])
        self.assertEqual(distribution_summary(np.array([0.,np.log(2)]),np.array([.5,.5]),'entry_adverse_log_loss',np.log(2))['brier'],0)

    def test_fair_scores_match_quadratic_formula_and_iid_expectation(self):
        atoms=np.array([-2.,1.,4.,5.]); weights=np.full(4,.25); observed=.5
        fair=distribution_summary(atoms,weights,'terminal_log_return',observed,interpretation='iid_predictive_law_draws')
        quadratic=np.mean(abs(atoms-observed))-.5*np.sum(abs(atoms[:,None]-atoms[None,:]))/(4*3)
        self.assertAlmostEqual(fair['crps'],quadratic)
        issued=distribution_summary(atoms,weights,'terminal_log_return',observed)
        self.assertEqual(issued['crps_mc_correction'],0)
        self.assertEqual(issued['brier_mc_correction'],0)
        self.assertGreater(issued['crps'],fair['crps'])
        support=np.array([-2.,1.]); probabilities=np.array([.25,.75]); n=3
        truth=distribution_summary(support,probabilities,'terminal_log_return',observed)
        expectation={'crps':0.,'brier':0.}; empirical=0.
        for indices in product(range(2),repeat=n):
            mass=float(np.prod(probabilities[list(indices)]))
            score=distribution_summary(support[list(indices)],np.full(n,1/n),'terminal_log_return',observed,
                                       interpretation='iid_predictive_law_draws')
            for field in expectation:expectation[field]+=mass*score[field]
            empirical+=mass*score['empirical_crps']
        self.assertAlmostEqual(expectation['crps'],truth['crps'])
        self.assertAlmostEqual(expectation['brier'],truth['brier'])
        self.assertGreater(empirical,truth['crps'])
        correlated=sum(probabilities[i]*distribution_summary(np.repeat(support[i],n),np.full(n,1/n),
                        'terminal_log_return',observed,interpretation='iid_predictive_law_draws')['crps'] for i in range(2))
        self.assertNotAlmostEqual(correlated,truth['crps'])
        bad=registration();bad['ensemble_interpretation']='correlated_paths'
        with self.assertRaisesRegex(ValueError,'iid path'):evaluate(self.snapshot,self.references,ToyModel(),bad)
        with self.assertRaisesRegex(ValueError,'equally weighted iid'):
            distribution_summary(support,probabilities,'terminal_log_return',observed,interpretation='iid_predictive_law_draws')
        tiny=distribution_summary(np.array([-1.,1.,1.]),np.full(3,1/3),'terminal_log_return',1.,
                                  interpretation='iid_predictive_law_draws')
        self.assertLess(tiny['brier'],0.)

    def test_failures_keep_requested_support_and_suppress_means(self):
        class Failing(ToyModel):
            def simulate(self, posterior, holding_days, *, seed):
                if seed%3==0: raise FloatingPointError('synthetic failure')
                return super().simulate(posterior,holding_days,seed=seed)
        report=evaluate(self.snapshot,self.references,Failing(),registration())
        failed=[c for c in report['cells'] if c['failure_n'] and c['scored_n']]
        self.assertTrue(failed)
        for cell in failed:
            self.assertIsNone(cell['means']['crps'])
            self.assertIsNotNone(cell['successful_subset_diagnostic']['crps'])
        clean=evaluate(self.snapshot,self.references,ToyModel(),registration())
        a={(c['support'],c['model'],c['replica'],c['role'],c['horizon'],c['target']):c['origins_id'] for c in report['cells']}
        b={(c['support'],c['model'],c['replica'],c['role'],c['horizon'],c['target']):c['origins_id'] for c in clean['cells']}
        self.assertEqual(a,b)

    def test_fit_failures_do_not_simulate_and_bad_reference_fails(self):
        class BadFit(ToyModel):
            def fit(self, returns):return ToyPosterior(float('nan'),{})
            def simulate(self,*args,**kwargs):raise AssertionError('must not simulate failed fit')
        report=evaluate(self.snapshot,self.references,BadFit(),registration())
        self.assertTrue(all(r['status']=='numerical_failure' and 'AssertionError' not in r['error']
                            for r in report['records'] if r['model']=='generative'))
        invalid=deepcopy(self.references);invalid[0]['source_sha256']='bad'
        with self.assertRaisesRegex(ValueError,'identity/protocol'):evaluate(self.snapshot,invalid,ToyModel(),registration())

    def test_cli_exclusive_hash_bound_toy_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary).resolve();source=directory/'source.csv'
            write_source(source,self.snapshot);snapshot=load_snapshot(source)
            reference=directory/'references.json';reference.write_bytes(canonical_bytes({'references':references(snapshot)}))
            model=ToyModel();adapter=types.SimpleNamespace(PROTOCOL=model.PROTOCOL,fit=model.fit,simulate=model.simulate,__file__=__file__)
            reg=registration();reg.update(source_sha256=sha(source.read_bytes()),reference_replay_sha256=sha(reference.read_bytes()),
                                         scorecard_code_sha256=code_identity(),model_module='synthetic_only_adapter',
                                         model_source_sha256=sha(Path(__file__).read_bytes()))
            registration_path=directory/'registration.json';registration_path.write_bytes(canonical_bytes(reg))
            output=directory/'run';args=['--source',str(source),'--reference-replay',str(reference),
                                         '--registration',str(registration_path),'--output-dir',str(output)]
            with patch('research.generative_forecast_scorecard.importlib.import_module',return_value=adapter), redirect_stdout(io.StringIO()):
                self.assertEqual(main(args),0)
            verify_packet(output)
            self.assertTrue((output/'matched_direct_cdf.md').exists())
            self.assertTrue((output/'all_generative_eligible.md').exists())
            with self.assertRaises(FileExistsError):main(args)
            changed=directory/'bad';reference.write_text('{}')
            with self.assertRaisesRegex(ValueError,'input hash mismatch'):
                main(args[:-1]+[str(changed)])
            verify_packet(changed)
            self.assertTrue((changed/'error.json').exists())

    def test_runtime_and_boundary_helper_changes_fail_before_fit(self):
        model=ToyModel()
        bad=registration();bad['runtime']['numpy']='different-runtime'
        with self.assertRaisesRegex(ValueError,'runtime mismatch'):
            evaluate(self.snapshot,self.references,model,bad)
        self.assertEqual(model.fit_inputs,[])
        for helper in ('scorecard_artifacts.py','market_scorecard.py'):
            bad=registration();self.assertIn(helper,bad['scorecard_code_sha256'])
            changed=dict(code_identity());changed[helper]='0'*64
            with patch('research.generative_forecast_scorecard.code_identity',return_value=changed):
                with self.assertRaisesRegex(ValueError,'code mismatch'):
                    evaluate(self.snapshot,self.references,model,bad)
            self.assertEqual(model.fit_inputs,[])

    def test_missing_price_blocks_exactly_affected_history_windows(self):
        source=deepcopy(self.snapshot);source['daily'][1000]['price']=None
        source['source_sha256']=digest(source['daily'])
        report=evaluate(source,references(source),ToyModel(),registration())
        missing=source['daily'][1000]['date']
        for row in report['eligibility']:
            if missing<=row['date']<=source['daily'][1730]['date']:self.assertFalse(row['eligible'])


if __name__=='__main__':unittest.main()
