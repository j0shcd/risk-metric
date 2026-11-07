from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import pandas as pd
from research import direct_cdf_campaign as c
from research.market_dataset import load_snapshot
from tests.test_market_scorecard import snapshot, write_source

class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.root=Path(self.temporary.name).resolve();self.bundle=self.root/'inputs';self.bundle.mkdir()
        source=self.bundle/'development_scores.csv';write_source(source,snapshot(40))
        self.manifest={'cutoff':'2022-12-31','sources':{source.name:{'development_sha256':c.sha(source.read_bytes())}}}
        (self.bundle/'manifest.json').write_text(json.dumps(self.manifest))
        self.csv=self.root/'candidate.csv'
        data=load_snapshot(source)
        pd.DataFrame({'Date':[r['date'] for r in data['monthly']],'signal':[r['dca_risk'] for r in data['monthly']]}).to_csv(self.csv,index=False)
        self.producer=self.root/'producer.py';self.producer.write_text('fixed generator')
        self.config=self.root/'config.json';self.config.write_text('{"fixed":true}')
        self.target=self.root/'campaign'
        self.spec={'global_budget':4,'worker_budgets':{'a':2,'b':2},'prior_exposure':{'parents':[],'statement':'synthetic fixtures only; no prior campaign','outer_history_exposed':True}}
        self.scorer=patch('research.indicator_trial.score_candidate',return_value={'dataset_id':'fixture','code_sha256':{},'cells':[]})
        self.references=patch('research.indicator_trial.baseline_candidates',return_value=[])
        self.scorer.start();self.references.start()
    def tearDown(self):
        self.references.stop();self.scorer.stop();self.temporary.cleanup()
    def create(self):return c.create_campaign(self.bundle,self.target,self.spec)
    def request(self,worker='a'):
        return {'worker':worker,'candidate_csv':str(self.csv),'column':'signal','name':'fixture_'+worker,
                'provenance':'synthetic','producer':str(self.producer),'config':str(self.config),'params':{'alpha':.08}}
    def frozen(self):
        self.create();result=c.submit(self.target,self.request());self.assertEqual(result['status'],'completed')
        c.freeze(self.target,[result['attempt']]);return result['attempt']
    def outer(self,attempt):
        source=self.bundle/'development_scores.csv'
        return {'source':str(source),'source_sha256':c.sha(source.read_bytes()),'candidates':[{
            'attempt':attempt,'csv':str(self.csv),'csv_sha256':c.sha(self.csv.read_bytes()),
            'producer':str(self.producer),'config':str(self.config),'params':{'alpha':.08}}]}

    def test_parallel_global_and_worker_caps(self):
        self.spec.update(global_budget=3,worker_budgets={'a':2,'b':2});self.create()
        def attempt(worker):
            try:return c.submit(self.target,self.request(worker))
            except ValueError as error:return str(error)
        with ThreadPoolExecutor(max_workers=6) as pool:
            results=list(pool.map(attempt,['a','a','a','b','b','b']))
        self.assertEqual(sum(isinstance(r,dict) for r in results),3)
        state=c.status(self.target);self.assertEqual(len(state['attempts']),3)
        for worker in ['a','b']:
            self.assertLessEqual(sum(r['worker']==worker for r in state['attempts']),2)
        self.assertEqual(len({r['attempt'] for r in state['attempts']}),3)

    def test_failures_and_interruptions_consume_budget(self):
        self.create();self.csv.write_text('invalid csv')
        result=c.submit(self.target,self.request());self.assertEqual(result['status'],'failed')
        with patch.object(c,'run_trial',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):c.submit(self.target,self.request())
        with self.assertRaisesRegex(ValueError,'budget'):c.submit(self.target,self.request())
        status=c.status(self.target)
        self.assertEqual([r['status'] for r in status['attempts']],['failed','reserved_or_interrupted'])
        with self.assertRaisesRegex(ValueError,'unresolved'):c.freeze(self.target,[result['attempt']])

    def test_freeze_serializes_with_inflight_submission(self):
        self.create();first=c.submit(self.target,self.request())
        entered=threading.Event();resume=threading.Event();original=c.run_trial
        def held(*args,**kwargs):
            entered.set();self.assertTrue(resume.wait(5));return original(*args,**kwargs)
        with patch.object(c,'run_trial',held),ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(c.submit,self.target,self.request('b'))
            self.assertTrue(entered.wait(5))
            with self.assertRaisesRegex(ValueError,'unresolved'):c.freeze(self.target,[first['attempt']])
            resume.set();self.assertEqual(future.result(timeout=10)['status'],'completed')
        c.freeze(self.target,[first['attempt']])
        with self.assertRaisesRegex(ValueError,'closed'):c.submit(self.target,self.request('b'))

    def test_corrupt_or_changed_campaign_identity_fails_closed(self):
        self.create()
        with patch.object(c,'runtime',return_value={'changed':True}):
            with self.assertRaisesRegex(ValueError,'identity'):c.status(self.target)
        with patch.object(c,'code_hashes',return_value={'changed':True}):
            with self.assertRaisesRegex(ValueError,'identity'):c.status(self.target)
        source=self.target/'bundle'/'development_scores.csv';source.chmod(0o600);source.write_text('corrupt')
        with self.assertRaisesRegex(ValueError,'corrupt'):c.submit(self.target,self.request())

    def test_future_inputs_rejected_and_explicit_lineage_required(self):
        bad={**self.spec,'prior_exposure':{}}
        with self.assertRaisesRegex(ValueError,'lineage'):c.create_campaign(self.bundle,self.target,bad)
        self.create();frame=pd.read_csv(self.csv);frame.loc[len(frame)]=['2023-01-31',.5];frame.to_csv(self.csv,index=False)
        self.assertEqual(c.submit(self.target,self.request())['status'],'failed')
        frame=pd.read_csv(self.bundle/'development_scores.csv');frame.iloc[-1,0]='2023-01-01';frame.to_csv(self.bundle/'development_scores.csv',index=False)
        self.manifest['sources']['development_scores.csv']['development_sha256']=c.sha((self.bundle/'development_scores.csv').read_bytes())
        (self.bundle/'manifest.json').write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(ValueError,'post-cutoff'):c.create_campaign(self.bundle,self.root/'future',self.spec)

    def test_one_release_under_concurrency_and_owned_inputs(self):
        attempt=self.frozen();request=self.outer(attempt)
        calls=[]
        def fake(source,registration):
            calls.append((source,registration))
            self.assertTrue(str(source).startswith(str(self.target/'release')))
            return {'results':[],'references':[]},{}
        def release():
            try:return c.release(self.target,request)
            except ValueError as error:return str(error)
        with patch.object(c,'run_replay',fake),ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:release(),range(2)))
        self.assertEqual(len(calls),1)
        self.assertEqual(sum(isinstance(r,dict) and r['status']=='completed' for r in results),1)
        self.assertEqual(c.status(self.target)['state'],'RELEASE_COMPLETE')
        with self.assertRaises(ValueError):c.release(self.target,request)

    def test_release_reserved_before_read_and_consumed_on_failure(self):
        attempt=self.frozen();request=self.outer(attempt);original=c.read_once;observed=[]
        def observe(path):
            if str(path)==request['source']:
                observed.append((self.target/'release'/'request.json').exists())
                raise OSError('simulated source read failure')
            return original(path)
        with patch.object(c,'read_once',observe),patch.object(c,'run_replay') as replay:
            result=c.release(self.target,request)
            self.assertEqual(result['status'],'failed');replay.assert_not_called()
        self.assertEqual(observed,[True])
        self.assertEqual(c.status(self.target)['state'],'RELEASE_RESERVED')
        with self.assertRaises(ValueError):c.release(self.target,request)

    def test_prefix_and_producer_identity_rejected_before_scoring(self):
        attempt=self.frozen();request=self.outer(attempt)
        frame=pd.read_csv(self.csv);frame.loc[0,'signal']+=.01;frame.to_csv(self.csv,index=False)
        request['candidates'][0]['csv_sha256']=c.sha(self.csv.read_bytes())
        with patch.object(c,'run_replay') as replay:
            result=c.release(self.target,request);replay.assert_not_called()
        self.assertEqual(result['status'],'failed');self.assertIn('prefix',result['reason'])

    def test_changed_producer_config_params_or_source_hash_rejects(self):
        for kind in ['producer','config','params','source_hash']:
            with self.subTest(kind=kind):
                self.target=self.root/('campaign_'+kind);attempt=self.frozen();request=self.outer(attempt)
                if kind in ['producer','config']:
                    changed=self.root/(kind+'_changed');changed.write_text('changed');request['candidates'][0][kind]=str(changed)
                elif kind=='params':request['candidates'][0]['params']={'alpha':.09}
                else:request['source_sha256']='0'*64
                with patch.object(c,'run_replay') as replay:
                    result=c.release(self.target,request);replay.assert_not_called()
                self.assertEqual(result['status'],'failed')
                self.assertTrue('changed' in result['reason'] or 'hash mismatch' in result['reason'])

    def test_budget_boundary_matches_slot_format(self):
        self.spec.update(global_budget=999,worker_budgets={'a':999})
        manifest=self.create();self.assertEqual(manifest['global_budget'],999)
        self.spec['global_budget']=1000
        with self.assertRaisesRegex(ValueError,'budget'):
            c.create_campaign(self.bundle,self.root/'invalid_budget',self.spec)
        self.spec.update(global_budget=999,worker_budgets={'a':1000})
        with self.assertRaisesRegex(ValueError,'budgets'):
            c.create_campaign(self.bundle,self.root/'invalid_worker_budget',self.spec)

    def test_monthly_component_revision_rejected_with_same_prices(self):
        attempt=self.frozen();request=self.outer(attempt)
        altered=self.root/'altered_source.csv'
        frame=pd.read_csv(request['source'])
        index=frame['dca_risk'].first_valid_index();frame.loc[index,'dca_risk']+=.01
        frame.to_csv(altered,index=False)
        request['source']=str(altered);request['source_sha256']=c.sha(altered.read_bytes())
        with patch.object(c,'run_replay') as replay:
            result=c.release(self.target,request);replay.assert_not_called()
        self.assertEqual(result['status'],'failed')
        self.assertIn('baseline/component',result['reason'])

    def test_interrupted_release_consumed_and_reported(self):
        attempt=self.frozen();request=self.outer(attempt)
        with patch.object(c,'run_replay',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):c.release(self.target,request)
        status=c.status(self.target)
        self.assertEqual(status['state'],'RELEASE_RESERVED')
        self.assertEqual(status['release_status'],'reserved_or_interrupted')
        with self.assertRaises(ValueError):c.release(self.target,request)

    def test_request_capture_survives_external_path_replacement(self):
        self.create();original=c.read_once;before=self.csv.read_bytes()
        def replace(path):
            payload=original(path)
            if str(path)==str(self.csv):self.csv.write_text('replaced after capture')
            return payload
        with patch.object(c,'read_once',replace):result=c.submit(self.target,self.request())
        self.assertEqual(result['status'],'completed')
        slot=self.target/'attempts'/result['attempt']
        self.assertEqual((slot/'candidate.csv').read_bytes(),before)

if __name__=='__main__':unittest.main()
