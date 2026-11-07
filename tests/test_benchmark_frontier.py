from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from research import benchmark_frontier as f
from research.market_dataset import digest, canonical_bytes
from research.scorecard_artifacts import write_packet
from research.generative_forecast_scorecard import evaluate, MODEL_FILE
from tests.test_generative_forecast_scorecard import fixture,registration,ToyModel
from research.market_information import baseline_candidates, score_candidate

def references(snapshot):
    return [score_candidate(snapshot,c) for c in baseline_candidates(snapshot)]


def seal(atlas):
    atlas.setdefault('reference_inventory',[(m['name'],m['replica']) for m in atlas['models']])
    atlas['atlas_id']=digest({k:v for k,v in atlas.items() if k!='atlas_id'});return atlas


def minimal_atlas(source):
    """Empty synthetic reference support for coordinator lifecycle-only tests."""
    return seal({'protocol':f.PROTOCOL,'identity':{'source_sha256':source},'code_sha256':f.code_identity(),
                 'runtime':f.runtime_identity(),'models':[
                     {'name':name,'replica':replica,'kind':kind,'records':[]}
                     for name,replica,kind in [*[("direct_cdf:"+name,None,"issued_cdf") for name in f.DIRECT_NAMES],('context',None,'issued_cdf'),
                                              ('unconditional',None,'issued_cdf'),('generative',0,'iid_predictive_law_draws'),
                                              ('generative',1,'iid_predictive_law_draws')]]})


class FrontierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name).resolve()
        snap=fixture('2022-12-31');cls.refs=references(snap);raw=canonical_bytes({'references':cls.refs})
        reg=registration();reg.update(reference_replay_sha256=f.sha(raw),source_sha256=snap['source_sha256'],model_source_sha256=f.sha(MODEL_FILE.read_bytes()))
        gen=evaluate(snap,cls.refs,ToyModel(),reg)
        for name,files in [('direct',{'replay.json':raw}),('gen',{'scorecard.json':canonical_bytes(gen),'registration.json':canonical_bytes(reg)})]:
            p=cls.root/name;p.mkdir();write_packet(p,files)
        cls.atlas=f.build_atlas(cls.root/'direct',cls.root/'gen');cls.trial={'result':cls.refs[0]}
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_issued_identity_and_compact_exact_support(self):
        report=f.compare_trial(self.atlas,self.trial)
        own=[c for c in report['cells'] if c['reference']=='direct_cdf:dca_risk' and c['scored_n']]
        self.assertTrue(own)
        self.assertTrue(all(c['reference_minus_candidate']['crps']==0 and c['reference_minus_candidate']['brier']==0 for c in own))
        self.assertEqual([c['ordinal_alignment'] for c in report['ordering_diagnostics']],[c['ordinal_alignment'] for c in self.trial['result']['cells']])
        self.assertLess(len(canonical_bytes(self.atlas)),f.MAX_ATLAS_BYTES)
        self.assertTrue(all('atoms' not in r and 'weights' not in r for m in self.atlas['models'] for r in m['records']))
        for c in report['cells']:
            if c['reference']=='generative':self.assertLessEqual(c['scored_n'],len(self.refs[0]['predictions']))

    def test_candidate_issued_atoms_not_stored_loss_or_mc_corrected(self):
        trial=deepcopy(self.trial)
        for r in trial['result']['predictions']:r['candidate_crps']=-999
        report=f.compare_trial(self.atlas,trial)
        self.assertTrue(all(c['reference_minus_candidate']['crps']==0 for c in report['cells'] if c['reference']=='direct_cdf:dca_risk' and c['scored_n']))

    def test_wrong_sources_origins_protocol_corrupt_and_drift(self):
        bad=deepcopy(self.trial);bad['result']['source_sha256']='wrong'
        with self.assertRaisesRegex(ValueError,'source'):f.compare_trial(self.atlas,bad)
        for change in ('missing','outcome','horizon'):
            bad=deepcopy(self.trial)
            if change=='missing':bad['result']['predictions'].pop()
            elif change=='outcome':bad['result']['predictions'][0]['outcome']=999
            else:bad['result']['predictions'][0]['horizon']=13
            with self.assertRaises(ValueError):f.compare_trial(self.atlas,bad)
        bad=deepcopy(self.atlas);bad['models'].pop()
        with self.assertRaises(ValueError):f.validate_atlas(bad,self.atlas['identity']['source_sha256'])
        bad=deepcopy(self.atlas);bad['models'].pop(0);bad['reference_inventory']=[(m['name'],m['replica']) for m in bad['models']];seal(bad)
        with self.assertRaisesRegex(ValueError,'every frozen'):f.validate_atlas(bad,self.atlas['identity']['source_sha256'])
        with patch.object(f,'code_identity',return_value={'changed':'code'}):
            with self.assertRaisesRegex(ValueError,'code'):f.compare_trial(self.atlas,self.trial)

    def test_mc_noise_and_brier_tradeoff_remain_separate(self):
        atlas=deepcopy(self.atlas);baseline={f.key(r):r for r in atlas['models'][0]['records']}
        for model in atlas['models']:
            if model['name']!='generative':continue
            for r in model['records']:
                if f.key(r) not in baseline or r['status']!='scored':continue
                b=baseline[f.key(r)];r['crps']=b['crps']+(.01 if model['replica']==0 else -.01)
                r['brier']=b['brier']-.02
        report=f.compare_trial(seal(atlas),self.trial)
        self.assertFalse(any(g['numerically_stable_gain'] for g in report['mc_guards']))
        cells=[c for c in report['cells'] if c['reference']=='generative' and c['replica']==0 and c['scored_n']]
        self.assertTrue(all(c['reference_minus_candidate']['crps']>0 and c['reference_minus_candidate']['brier']<0 for c in cells))
        # Same sign, but larger replica noise than the registered 20% guard.
        for model in atlas['models']:
            if model['name']=='generative' and model['replica']==1:
                for r in model['records']:
                    if f.key(r) in baseline and r['status']=='scored':r['crps']=baseline[f.key(r)]['crps']+.02
        report=f.compare_trial(seal(atlas),self.trial)
        self.assertFalse(any(g['numerically_stable_gain'] for g in report['mc_guards']))
        for model in atlas['models']:
            if model['name']=='generative':
                for r in model['records']:
                    if f.key(r) in baseline and r['status']=='scored':r['crps']=baseline[f.key(r)]['crps']+.01
        report=f.compare_trial(seal(atlas),self.trial)
        self.assertTrue(any(g['numerically_stable_gain'] for g in report['mc_guards'] if g['metric']=='crps'))
        self.assertFalse(any(g['numerically_stable_gain'] for g in report['mc_guards'] if g['metric']=='brier'))

    def test_synthetic_campaign_end_to_end_without_comparison_mocks(self):
        from research import direct_cdf_campaign as campaign
        from research.market_dataset import load_snapshot
        from tests.test_market_scorecard import write_source
        import pandas as pd
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();bundle=root/'bundle';bundle.mkdir()
            source=bundle/'development_scores.csv';write_source(source,fixture('2022-12-31'))
            snapshot=load_snapshot(source);refs=references(snapshot);raw=canonical_bytes({'references':refs})
            (bundle/'manifest.json').write_bytes(canonical_bytes({'cutoff':'2022-12-31','sources':{source.name:{'development_sha256':f.sha(source.read_bytes())}}}))
            reg=registration();reg.update(reference_replay_sha256=f.sha(raw),source_sha256=snapshot['source_sha256'],model_source_sha256=f.sha(MODEL_FILE.read_bytes()))
            gen=evaluate(snapshot,refs,ToyModel(),reg)
            direct=root/'direct';direct.mkdir();write_packet(direct,{'replay.json':raw})
            generated=root/'generated';generated.mkdir();write_packet(generated,{'scorecard.json':canonical_bytes(gen),'registration.json':canonical_bytes(reg)})
            atlas=f.build_atlas(direct,generated);atlas_path=root/'atlas.json';atlas_path.write_bytes(canonical_bytes(atlas))
            target=root/'campaign';campaign.create_campaign(bundle,target,{'benchmark_atlas':str(atlas_path),'global_budget':1,'worker_budgets':{'test':1},'prior_exposure':{'parents':[],'statement':'synthetic end-to-end only','outer_history_exposed':False}})
            candidate=root/'candidate.csv';pd.DataFrame({'Date':[r['date'] for r in snapshot['monthly']],'value':[r['dca_risk'] for r in snapshot['monthly']]}).to_csv(candidate,index=False)
            producer=root/'producer';producer.write_text('synthetic');config=root/'config';config.write_text('{}')
            result=campaign.submit(target,{'worker':'test','candidate_csv':str(candidate),'column':'value','name':'toy','provenance':'synthetic','producer':str(producer),'config':str(config),'params':{}})
            self.assertEqual(result['status'],'completed',result)
            comparison=json.loads((target/'attempts'/result['attempt']/'frontier.json').read_bytes())
            self.assertEqual(comparison['atlas_id'],atlas['atlas_id'])
            self.assertTrue(all(c['reference_minus_candidate']['crps']==0 for c in comparison['cells'] if c['reference']=='direct_cdf:dca_risk' and c['scored_n']))
            campaign.freeze(target,[result['attempt']]);self.assertEqual(campaign.status(target)['state'],'FROZEN')

    def test_failures_and_pending_not_dropped(self):
        atlas=deepcopy(self.atlas);r=next(r for r in atlas['models'][-1]['records'] if r['status']=='scored' and f.key(r) in f.mapping(atlas['models'][0]['records']))
        r['status']='numerical_failure';r['error']='synthetic failure'
        report=f.compare_trial(seal(atlas),self.trial)
        cell=next(c for c in report['cells'] if c['reference']=='generative' and c['replica']==1 and all(c[k]==r[k] for k in ('role','horizon','target')))
        self.assertEqual(cell['failure_n'],1);self.assertTrue(all(v is None for v in cell['reference_minus_candidate'].values()))
        self.assertTrue(any(c['unavailable_n'] for c in report['cells']))

if __name__=='__main__':unittest.main()
