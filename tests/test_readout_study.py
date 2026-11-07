import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from research import readout_study as study

class ReadoutTests(unittest.TestCase):
    def test_training_only_percentiles_and_monotonic_invariance(self):
        x=np.arange(24.)[:,None]
        ranks,q=study.percentile(x,np.array([100.]))
        np.testing.assert_allclose(ranks[:,0],(np.arange(24)+.5)/24)
        self.assertEqual(q[0],1.)
        w,_=study.decode(x,np.array([12.2]),'rank')
        transformed,_=study.decode(np.exp(x),np.exp([12.2]),'rank')
        np.testing.assert_allclose(w,transformed)
        # Duplicate context cannot be extra information for the median readout.
        a,_=study.decode(np.c_[x,x],np.array([12.,12.]),'median')
        b,_=study.decode(x,np.array([12.]),'median')
        np.testing.assert_array_equal(a,b)

    def test_fractional_boundary_ties_and_permutation(self):
        x=np.r_[np.zeros(6),np.ones(6),np.full(12,2.)][:,None]
        w,info=study.decode(x,np.array([0.]),'rank')
        local=(w-1/48)*16
        np.testing.assert_allclose(local[:6],1.)
        np.testing.assert_allclose(local[6:12],1/3)
        np.testing.assert_allclose(local[12:],0.)
        self.assertEqual(info['local_mass'],8.)
        perm=np.arange(23,-1,-1)
        p,_=study.decode(x[perm],np.array([0.]),'rank')
        np.testing.assert_allclose(w,p[perm])
        flat,info=study.decode(np.ones((24,2)),np.ones(2),'rank')
        np.testing.assert_allclose(flat,1/24)
        self.assertAlmostEqual(info['weight_concentration_n'],24.)

    def test_empty_median_cell_falls_back_without_added_shrinkage(self):
        x=np.arange(24.)[:,None]
        base,_=study.decode(x,np.array([23.]),'median')
        w,info=study.decode(np.c_[x,x],np.array([23.,0.]),'median',base)
        np.testing.assert_array_equal(w,base)
        self.assertTrue(info['fallback'])
        w,_=study.decode(np.ones((24,1)),np.array([2.]),'median')
        np.testing.assert_allclose(w,1/24)

    def test_log_events_and_coverage(self):
        threshold=np.log(2.)
        for target in ['entry_adverse_log_loss','peak_drawdown_log_loss']:
            self.assertEqual(study.event_mask([.5,threshold,threshold+.01],target).tolist(),[False,False,True])
        self.assertEqual(study.event_mask([-.01,0,.01],'terminal_log_return').tolist(),[True,False,False])
        out=study.diagnostics(np.array([0.,1.]),np.array([.5,.5]),2.,'peak_drawdown_log_loss')
        self.assertEqual(out['event_probability'],.5)
        self.assertEqual(out['brier'],.25)
        self.assertTrue(out['outside_atom_range'])
        self.assertFalse(out['coverage_80'])
        self.assertEqual(out['width_80'],1.)
        self.assertAlmostEqual(out['crps'],1.25)

    def test_common_support_strict_maturity_and_future_suffix(self):
        dates=pd.date_range('2015-01-31',periods=32,freq='ME')
        rows=[]
        for i,d in enumerate(dates):
            rows.append({'date':d.date().isoformat(),'context':[float(i),float(i%3)],
                         'outcomes':{str(h):{'status':'complete','available':(d+pd.Timedelta(days=1)).date().isoformat(),
                                             'values':[i/20.,i/40.,i/30.]} for h in [12,24]}})
        candidate={'name':'test','direction':'higher_risk','provenance':'deterministic test','values':[{'date':r['date'],'value':float(i)} for i,r in enumerate(rows)]}
        snapshot={'daily':[{'date':'2022-12-31'}]}
        with patch.object(study,'build_dataset',return_value={'rows':rows}):
            a=study.evaluate(snapshot,[candidate])
        self.assertEqual(len(a['support']['12']),8)
        self.assertTrue(all(r['last_train_label_available']<r['date'] for r in a['predictions']))
        self.assertTrue(all(c['n']==8 for c in a['cells']))
        changed={**candidate,'values':[dict(v) for v in candidate['values']]}
        changed['values'][-1]['value']=1e8
        with patch.object(study,'build_dataset',return_value={'rows':rows}):
            b=study.evaluate(snapshot,[changed])
        self.assertEqual([r for r in a['predictions'] if r['date']<rows[-1]['date']],
                         [r for r in b['predictions'] if r['date']<rows[-1]['date']])
        # A label becoming available exactly at the origin is not strictly mature.
        import copy
        delayed=copy.deepcopy(rows)
        for h in ['12','24']:
            delayed[0]['outcomes'][h]['available']=rows[24]['date']
        with patch.object(study,'build_dataset',return_value={'rows':delayed}):
            c=study.evaluate(snapshot,[candidate])
        self.assertEqual(len(c['support']['12']),7)
        self.assertNotIn(rows[24]['date'],c['support']['12'])
        with self.assertRaises(ValueError):
            study.evaluate({'daily':[{'date':'2023-01-01'}]},[candidate])

if __name__=='__main__': unittest.main()
