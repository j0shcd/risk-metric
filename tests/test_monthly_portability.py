from contextlib import redirect_stdout
import io
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from research import monthly_portability as m
from research.scorecard_artifacts import verify_packet

class MonthlyPortabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dates=pd.date_range('1970-01-31','2022-12-31',freq='ME')
        t=np.arange(len(dates))
        cls.prices=pd.Series(100*np.exp(.003*t+.25*np.sin(t/15)+.10*np.sin(t/4)),index=dates)
        cls.dataset=m.build_dataset(cls.prices)
    def row(self,dataset,date):return next(r for r in dataset['rows'] if r['date']==date)
    def index(self,dataset,date):return next(i for i,r in enumerate(dataset['rows']) if r['date']==date)

    def test_calendar_entry_leap_exit_and_path_targets(self):
        prices=self.prices.copy();prices[:]=100.
        prices.loc['2000-01-31']=1000.  # Decision price is NOT entry.
        prices.loc['2000-03-31']=200.;prices.loc['2000-04-30']=80.;prices.loc['2001-02-28']=120.
        row=self.row(m.build_dataset(prices),'2000-01-31')['outcomes']['12']
        self.assertEqual(row['entry'],'2000-02-29');self.assertEqual(row['end'],'2001-02-28')
        self.assertEqual(row['available'],'2001-03-01')
        np.testing.assert_allclose(row['values'],[np.log(1.2),np.log(1.25),np.log(2.5)],atol=1e-14)

    def test_context_and_signed_trailing_peak_reference_formula(self):
        query='2000-01-31';row=self.row(self.dataset,query)
        history=self.prices.loc[:query];logs=np.log(history)
        self.assertAlmostEqual(row['context'][0],logs.iloc[-1]-logs.iloc[-13])
        self.assertAlmostEqual(row['context'][1],logs.diff().iloc[-12:].std(ddof=1))
        self.assertAlmostEqual(row['features']['monthly_log_sma_12m'],np.log(history.iloc[-1]/history.iloc[-12:].mean()))
        self.assertAlmostEqual(row['features']['monthly_drawdown_12m'],logs.iloc[-1]-logs.iloc[-13:].max())
        # A recovered historical crash has zero current underwater distance but
        # nonzero historical max drawdown: the frozen reference is the former.
        p=self.prices.copy();p.loc['1999-01-31':'2000-01-31']=100.
        p.loc['1999-04-30']=200.;p.loc['1999-05-31']=50.;p.loc[query]=200.
        result=self.row(m.build_dataset(p),query)['features']['monthly_drawdown_12m']
        self.assertEqual(result,0.)

    def test_a_lag_and_future_suffix_truncation_invariance(self):
        query='2000-01-31';index=self.index(self.dataset,query)
        changed=self.prices.copy();changed.loc[query]*=2
        current=self.row(m.build_dataset(changed),query)
        original=self.dataset['rows'][index]
        self.assertEqual(current['features']['swing_a_memory_0'],original['features']['swing_a_memory_0'])
        self.assertNotEqual(current['features']['swing_b_adaptive'],original['features']['swing_b_adaptive'])
        suffix=self.prices.copy();suffix.loc[suffix.index>query]*=100
        altered=m.build_dataset(suffix);truncated=m.build_dataset(self.prices.loc[:query])
        for horizon in [12,24,48]:
            baseline=m.forecast_origin(self.dataset,index,horizon)
            for data in [altered,truncated]:
                other=m.forecast_origin(data,self.index(data,query),horizon)
                self.assertEqual(baseline['train_dates'],other['train_dates'])
                np.testing.assert_array_equal(baseline['atoms'],other['atoms'])
                for name in baseline['weights']:np.testing.assert_array_equal(baseline['weights'][name],other['weights'][name])

    def test_strict_maturity_and_exact_context_duplicates(self):
        dataset=copy.deepcopy(self.dataset);index=self.index(dataset,'1990-01-31')
        for horizon in [12,24,48]:
            pool=m.mature_pool(dataset['rows'],index,horizon)
            self.assertEqual(len(pool),24)
            last=pool[-1];dataset['rows'][last]['outcomes'][str(horizon)]['available']='1990-01-31'
            self.assertNotIn(last,m.mature_pool(dataset['rows'],index,horizon))
        forecast=m.forecast_origin(dataset,index,24)
        self.assertLess(forecast['last_training_label_available'],'1990-01-31')
        for name in ['monthly_trend_12m','monthly_volatility_12m']:
            np.testing.assert_array_equal(forecast['weights'][name],forecast['weights']['context_only'])
        self.assertEqual(forecast['atoms'].shape,(24,3))
        self.assertEqual(len(forecast['weights']),13)

    def test_class_counts_closed_intervals_and_one_class_warning(self):
        records=[{'entry':'2000-01-31','end':'2004-01-31','event_occurred':False,'training_event_n':0},
                 {'entry':'2004-01-31','end':'2008-01-31','event_occurred':False,'training_event_n':0},
                 {'entry':'2004-02-29','end':'2008-02-29','event_occurred':False,'training_event_n':0}]
        counts=m.class_support(records)
        self.assertEqual(counts['event_n'],0);self.assertEqual(counts['non_event_n'],3)
        self.assertEqual(counts['nonoverlap_non_event_n'],2)
        self.assertEqual(m.nonoverlap_count(records[:2]),1)
        self.assertEqual(counts['event_discrimination'],'not_established_single_class')
        self.assertEqual(counts['one_class_training_pools'],3)
        self.assertIn('cannot be added',counts['nonoverlap_note'])
        for target in m.TARGETS[1:]:
            self.assertEqual(m.event_mask([.5,np.log(2),np.log(2)+.01],target).tolist(),[False,False,True])

    def test_input_boundaries_and_registration_json_roundtrip(self):
        for invalid in [self.prices.drop(self.prices.index[10]),pd.concat([self.prices,self.prices.iloc[-1:]]),self.prices.iloc[1:]]:
            with self.assertRaises(ValueError):m.build_dataset(invalid)
        future=pd.concat([self.prices,pd.Series([100.],index=[pd.Timestamp('2023-01-31')])])
        with self.assertRaisesRegex(ValueError,'post2022'):m.build_dataset(future)
        bad=self.prices.copy();bad.iloc[10]=0
        with self.assertRaises(ValueError):m.build_dataset(bad)
        registered=m.registration()
        self.assertEqual(registered,json.loads(json.dumps(registered)))
        self.assertEqual(registered['protocol']['candidate_parameters']['swing_a_memory_0']['memory_weight'],0.)
        self.assertEqual(registered['source_sha256'],'54b4aeb41fc12fb4d77034d946bb13be6036742e0a61fa63551d6ceb7d2b5374')

    def test_private_output_and_identity_fail_before_source_read(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw).resolve();registered=root/'registration.json'
            registered.write_text(json.dumps(m.registration()))
            with self.assertRaisesRegex(ValueError,'private'):
                m.run(root/'nonexistent_source.csv',registered,root/'public_output')
            altered=m.registration();altered['source_sha256']='bad';registered.write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError,'identity'):
                m.run(root/'nonexistent_source.csv',registered,root/'public_output')

    def test_unmocked_synthetic_cli_and_single_class_zero_loss(self):
        # Only identity/private-root are substituted. All generators, actual CDF
        # fitting, scoring, CLI dispatch and receipt publication execute unchanged.
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw).resolve();source=root/'invented_monthly.csv'
            pd.DataFrame({'Date':self.prices.index,'market_total_return_index':100.}).to_csv(source,index=False)
            registered=m.registration()
            registered.update(source_sha256=m.sha(source.read_bytes()),source_rows=len(self.prices),
                              source_first_month='1970-01-31',source_last_month='2022-12-31',synthetic_test_only=True)
            registered.pop('registration_id');registered['registration_id']=m.digest(registered)
            registration_path=root/'registered.json';private=root/'private';output=private/'run'
            with patch.object(m,'registration',return_value=registered),patch.object(m,'PRIVATE_ROOT',private):
                with patch('sys.argv',['monthly_portability','register','--registration',str(registration_path)]),redirect_stdout(io.StringIO()):
                    m.main()
                with patch('sys.argv',['monthly_portability','run','--registration',str(registration_path),'--source',str(source),'--output-dir',str(output)]),redirect_stdout(io.StringIO()):
                    m.main()
                with self.assertRaises(FileExistsError):m.run(source,registration_path,output)
            verify_packet(output)
            result=json.loads((output/'result.json').read_bytes())
            self.assertEqual(len(result['cells']),234)
            self.assertEqual(len(result['predictions']),39312)
            self.assertEqual(len(result['class_support']),18)
            for cell in result['cells']:
                self.assertEqual(cell['n'],168)
                self.assertEqual(cell['crps'],0.)
                self.assertEqual(cell['brier'],0.)
                self.assertIsNone(cell['alignment'])
                self.assertIsNone(cell['brier_skill_vs_unconditional'])
                self.assertEqual(cell['brier_skill_status_vs_unconditional'],'undefined_zero_reference_loss')
            for support in result['class_support']:
                self.assertEqual(support['outcome_n'],168)
                self.assertEqual(support['forecast_n'],168)
                self.assertEqual(support['event_n'],0)
                self.assertEqual(support['one_class_training_pools'],168)
                self.assertEqual(support['event_discrimination'],'not_established_single_class')
                self.assertEqual(support['training_event_counts'],[0]*168)
                if support['target']==m.TARGETS[0]:
                    self.assertEqual(support['negative_return_n'],0)
                    self.assertEqual(support['nonnegative_return_n'],168)

    def test_fixed_comparator_and_two_era_direction_rejection(self):
        cells=[]
        for model in (*m.CANDIDATES,'unconditional','context_only',*m.REFERENCES):
            for era in m.ERAS:
                for target in m.TARGETS:
                    cells.append({'model':model,'era':era,'horizon':24,'target':target,
                                  'crps':2. if model in m.CANDIDATES else 1.,'alignment':-.2})
        result=m.rejection_patterns(cells)
        for value in result.values():
            self.assertTrue(value['negative24m_return_alignment_both_eras'])
            self.assertIn('unconditional',value['same_comparator_24m_dominance_both_eras'])
        for cell in cells:
            if cell['model'] in m.CANDIDATES:
                cell['crps']=.5;cell['alignment']=None
        for value in m.rejection_patterns(cells).values():
            self.assertFalse(value['negative24m_return_alignment_both_eras'])
            self.assertEqual(value['same_comparator_24m_dominance_both_eras'],[])

if __name__=='__main__':unittest.main()


class MonthlyReceiptLifecycleTests(unittest.TestCase):
    def test_failed_reserved_attempt_is_bound_and_tamper_evident(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();source=root/'source.csv';source.write_bytes(b'invented bad source')
            reg=root/'registration.json';record=m.registration();reg.write_text(json.dumps(record))
            output=root/'attempt'
            with patch.object(m,'PRIVATE_ROOT',root):
                with self.assertRaisesRegex(ValueError,'source size/hash'):m.run(source,reg,output)
            receipt=verify_packet(output)
            self.assertEqual(set(receipt['files']),{'request.json','error.json','COMPLETE'})
            self.assertEqual(json.loads((output/'error.json').read_bytes())['status'],'failed_no_discard_or_retuning')
            (output/'error.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'corrupt'):verify_packet(output)

    def test_interrupted_reservation_is_visible_and_not_reusable(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();source=root/'source.csv';source.write_bytes(b'invented')
            reg=root/'registration.json';reg.write_text(json.dumps(m.registration()));output=root/'attempt'
            original_open=Path.open
            def interrupted(path,*args,**kwargs):
                if path==source:raise KeyboardInterrupt
                return original_open(path,*args,**kwargs)
            with patch.object(m,'PRIVATE_ROOT',root),patch.object(Path,'open',interrupted):
                with self.assertRaises(KeyboardInterrupt):m.run(source,reg,output)
            self.assertTrue((output/'request.json').exists())
            with self.assertRaisesRegex(ValueError,'incomplete'):verify_packet(output)
            with patch.object(m,'PRIVATE_ROOT',root):
                with self.assertRaises(FileExistsError):m.run(source,reg,output)
