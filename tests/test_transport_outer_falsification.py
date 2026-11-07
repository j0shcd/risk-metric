"""Synthetic calendar/receipt oracles only; no real outer evaluation."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from research import transport_outer_falsification as m
from research.market_dataset import COMPONENTS,canonical_bytes,digest,load_snapshot,build_dataset
from research.scorecard_artifacts import write_packet,verify_packet


def fixture(root):
    dates=pd.date_range('2012-01-01','2026-07-30',freq='D');t=np.arange(len(dates))
    frame=pd.DataFrame({'btc_price':np.exp(4+t*.0003+.2*np.sin(t/93))},index=dates)
    for c in COMPONENTS:frame[c]=np.where(dates>=pd.Timestamp('2014-12-31'),.5,np.nan)
    source=root/'full.csv';frame.to_csv(source);snapshot=load_snapshot(source)
    development=root/'development.csv';frame.loc[:'2022-12-31'].to_csv(development);dev=load_snapshot(development)
    snapshot_path=root/'snapshot.json';snapshot_path.write_bytes(canonical_bytes(snapshot))
    rows,features=m.prepared(dev);old=[]
    for i,row in enumerate(rows):
        for h in (12,24):
            o=row['outcomes'][str(h)]
            if o['status']=='complete' and o['available']<='2022-12-31' and len(m.pool(rows,i,h))==24:
                old.extend(m.forecast(rows,features,i,h,name,'development') for name in m.MODELS)
    current=m.identity()
    # The prior experiment's inventory is historical; unrelated new modules must
    # not be retroactively added to that synthetic prior's 43-file closure.
    prior_names=json.loads((m.ROOT/'docs/artifacts/return-transport-registration-2026-11-07.json').read_bytes())['code']
    prior_code={name:current['code'][name] for name in prior_names}
    assert len(prior_code)==43
    priorreg={'protocol':m.KERNEL_PROTOCOL,'inputs':{'source':{'sha256':m.sha(development.read_bytes())}},'code':prior_code,'runtime':current['runtime']}
    priorreg['registration_id']=digest(priorreg)
    prior=root/'prior';prior.mkdir();write_packet(prior,{'registration.json':canonical_bytes(priorreg),'study.json':canonical_bytes({'protocol':m.KERNEL_PROTOCOL,'registration_id':priorreg['registration_id'],'records':old})})
    rows,_=m.prepared(snapshot);predictions=[]
    for i,row in enumerate(rows):
        if row['date']<'2023-01-01':continue
        for h in (12,24):
            o=row['outcomes'][str(h)]
            if o['status']!='complete' or o['available']>snapshot['daily'][-1]['date']:continue
            pool=m.pool(rows,i,h);atoms=[rows[j]['outcomes'][str(h)]['values'][0] for j in pool];weights=[1/24]*24
            crps=m.diagnostics(np.array(atoms),np.array(weights),o['values'][0],'terminal_log_return')['crps']
            predictions.append({'date':row['date'],'horizon':h,'target':'terminal_log_return','role':'outer','outcome':o['values'][0],
                                'entry':o['entry'],'end':o['end'],'label_available':o['available'],'atoms':atoms,
                                'train_dates':[rows[j]['date'] for j in pool],'candidate_weights':weights,'reference_weights':weights,
                                'candidate_crps':crps,'reference_crps':crps,'unconditional_crps':crps})
    common={'source_sha256':snapshot['source_sha256'],'dataset_id':digest(build_dataset(snapshot,[12,24,48])),
            'snapshot_id':digest(snapshot),'protocol':m.CDF_PROTOCOL,'minimum_training':24,'as_of':snapshot['daily'][-1]['date'],
            'development_cutoff':'2022-12-31','outer_start':'2023-01-01',
            'code_sha256':{name:m.sha((m.ROOT/'research'/name).read_bytes()) for name in ('market_information.py','market_dataset.py','market_scorecard.py','distribution_readout.py')},'predictions':predictions}
    references=root/'references';references.mkdir();write_packet(references,{'replay.json':canonical_bytes({'source_sha256':snapshot['source_sha256'],'references':[{**common,'candidate_name':name} for name in m.DIRECT_NAMES]})})
    reg=m.build_registration(snapshot_path,development,prior,references)
    return reg,m.capture(reg)


class OuterFalsificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name).resolve();cls.reg,cls.payload=fixture(cls.root)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_unmocked_registered_lifecycle_prefix_and_missing_generators(self):
        path=self.root/'registration.json';path.write_bytes(canonical_bytes(self.reg));out=self.root/'complete'
        result=m.run(path,out);receipt=verify_packet(out)
        self.assertIn('inputs.json',receipt['files']);self.assertEqual(result['development_prefix']['verified_forecasts'],216)
        self.assertEqual(len(result['records']),144);self.assertEqual(len(result['reference_records']),720)
        self.assertEqual(len(result['cells']),108)
        self.assertTrue(all(r['date']>='2023-01-01' and r['role']=='outer' for r in result['records']))
        for h,n in ((12,30),(24,18)):
            for name in m.MODELS:self.assertEqual(sum(r['horizon']==h and r['model']==name for r in result['records']),n)
        self.assertEqual(result['generative_outer'],[{'replica':i,'status':'unavailable_not_computed','comparison':None} for i in (0,1)])
        self.assertTrue(all(c['reference']!='generative' for c in result['cells']))
        age=[c for c in result['cells'] if c['model']==m.MODELS[2] and c['horizon']==24]
        context=next(c for c in age if c['reference']=='context');self.assertEqual(result['stopping']['incremental_contribution_fails'],context['reference_minus_model']['crps']<=0)
        self.assertTrue(any(c['reference']=='context_cdf' for c in age))
        with self.assertRaises(FileExistsError):m.run(path,out)

    def test_prefix_price_and_forecast_tampering(self):
        payload=deepcopy(self.payload);snapshot=json.loads(payload['snapshot']);snapshot['daily'][100]['price']*=2;payload['snapshot']=canonical_bytes(snapshot)
        with patch.object(m,'transport') as fit:
            with self.assertRaisesRegex(ValueError,'prefix'):m.evaluate(payload)
            fit.assert_not_called()
        payload=deepcopy(self.payload);prior=json.loads(payload['prior:study.json']);prior['records'][0]['atoms'][0]+=.01;payload['prior:study.json']=canonical_bytes(prior)
        with self.assertRaisesRegex(ValueError,'development forecast changed'):m.evaluate(payload)

    def test_prior_code_extension_and_drift(self):
        self.assertGreaterEqual(len(self.reg['code']),44)
        payload=deepcopy(self.payload);prior=json.loads(payload['prior:registration.json']);prior['code']['research/market_dataset.py']='0'*64
        prior['registration_id']=digest({k:v for k,v in prior.items() if k!='registration_id'});study=json.loads(payload['prior:study.json']);study['registration_id']=prior['registration_id']
        payload.update({'prior:registration.json':canonical_bytes(prior),'prior:study.json':canonical_bytes(study)})
        with patch.object(m,'transport') as fit:
            with self.assertRaisesRegex(ValueError,'prior recorded code'):m.evaluate(payload)
            fit.assert_not_called()

    def test_reference_horizon_outcome_and_support_before_fit(self):
        for mode in ('missing','outcome','end','atoms','family'):
            payload=deepcopy(self.payload);replay=json.loads(payload['references:replay.json'])
            if mode=='missing':replay['references'][0]['predictions'].pop()
            elif mode=='family':replay['references'].pop()
            elif mode=='atoms':replay['references'][0]['predictions'][0]['atoms'][0]+=.1
            else:replay['references'][0]['predictions'][0][mode]=99 if mode=='outcome' else '2024-02-02'
            payload['references:replay.json']=canonical_bytes(replay)
            with self.subTest(mode=mode),patch.object(m,'transport') as fit:
                with self.assertRaises(ValueError):m.evaluate(payload)
                fit.assert_not_called()

    def test_strict_label_clock_and_calendar_endpoints(self):
        snapshot=json.loads(self.payload['snapshot']);rows,_=m.prepared(snapshot)
        row=next(r for r in rows if r['date']=='2023-01-31');o=row['outcomes']['12']
        self.assertEqual((o['entry'],o['end'],o['available']),('2023-02-01','2024-02-01','2024-02-02'))
        tiny=[{'date':'2020-01-31','outcomes':{'12':{'status':'complete','available':'2023-01-31'}}},
              {'date':'2020-02-29','outcomes':{'12':{'status':'complete','available':'2023-01-30'}}},
              {'date':'2023-01-31'}]
        self.assertEqual(m.pool(tiny,2,12),[1])
        self.assertEqual(m.nonoverlap([{'entry':'2020-01-01','end':'2021-01-01'},{'entry':'2021-01-01','end':'2022-01-01'},{'entry':'2021-01-02','end':'2022-01-02'}]),2)

    def test_unrelated_code_inventory_growth_preserves_prior_contract(self):
        extended=deepcopy(m.identity())
        extended['code']['research/unrelated_future_module.py']='9'*64
        with tempfile.TemporaryDirectory() as temporary,patch.object(m,'identity',return_value=extended):
            reg,payload=fixture(Path(temporary).resolve())
            self.assertEqual(len(json.loads(payload['prior:registration.json'])['code']),43)
            self.assertIn('research/unrelated_future_module.py',reg['code'])
            snapshot,prior,refs=m.validate_inputs(payload)
            self.assertEqual(len(snapshot['monthly']),139)
            self.assertEqual(len(prior['records']),216)
            self.assertEqual(len(refs),13)

    def test_registration_failures_bind_exact_bytes_without_fit(self):
        for name,raw in [('malformed',b'{'),('runtime',canonical_bytes({**self.reg,'runtime':{'wrong':True}}))]:
            path=self.root/(name+'.json');path.write_bytes(raw)
            with patch.object(m,'transport') as fit:
                with self.assertRaises(ValueError):m.run(path,self.root/name)
                fit.assert_not_called()
            self.assertEqual((self.root/name/'registration.json').read_bytes(),raw);verify_packet(self.root/name)
        for field in ('runtime','code'):
            drift=deepcopy(self.reg);drift[field]={'changed':'identity'};drift['registration_id']=digest({k:v for k,v in drift.items() if k!='registration_id'})
            with self.assertRaisesRegex(ValueError,'code/runtime'):m.capture(drift)
        bad=deepcopy(self.reg);bad['inputs']['snapshot']['sha256']='0'*64;bad['registration_id']=digest({k:v for k,v in bad.items() if k!='registration_id'})
        with patch.object(m,'transport') as fit:
            with self.assertRaisesRegex(ValueError,'input identity'):m.capture(bad)
            fit.assert_not_called()
        path=self.root/'bad-input.json';path.write_bytes(canonical_bytes(bad));out=self.root/'bad-input'
        with self.assertRaisesRegex(ValueError,'input identity'):m.run(path,out)
        verify_packet(out);captured=json.loads((out/'inputs.json').read_bytes())
        self.assertEqual((out/captured['snapshot']['file']).read_bytes(),self.payload['snapshot'])

if __name__=='__main__':unittest.main()
