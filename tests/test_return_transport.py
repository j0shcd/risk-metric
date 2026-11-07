import unittest
import numpy as np
from research.return_transport import design,transport,registration

class TransportTests(unittest.TestCase):
    def setUp(self):
        self.rng=np.random.default_rng(20110417)
        self.x=self.rng.normal(size=(24,3));self.q=np.array([.3,-.7,1.])
        self.y=self.rng.normal(size=24)

    def test_press_independent_deleted_label_refits(self):
        x,q=design(self.x,self.q);actual=transport(self.x,self.q,self.y)
        residual=[]
        for i in range(24):
            keep=np.arange(24)!=i
            # Independent augmented least squares, fixed design and fixed24 penalty.
            penalty=np.diag([0.]+[np.sqrt(24)]*(x.shape[1]-1))
            beta=np.linalg.lstsq(np.vstack([x[keep],penalty]),np.r_[self.y[keep],np.zeros(x.shape[1])],rcond=None)[0]
            residual.append(self.y[i]-x[i]@beta)
        np.testing.assert_allclose(actual['loo_residuals'],residual,atol=1e-12)
        np.testing.assert_allclose(actual['atoms'],np.array(residual)+actual['location'],atol=1e-12)

    def test_intercept_is_inflated_pool_not_unconditional(self):
        result=transport(np.empty((24,0)),np.empty(0),self.y)
        np.testing.assert_allclose(result['atoms'],self.y.mean()+24/23*(self.y-self.y.mean()),atol=1e-12)
        self.assertEqual(result['coordinate_n'],0)

    def test_equivalent_coordinates_and_constants(self):
        original=transport(self.x,self.q,self.y)
        x=np.column_stack([self.x,-self.x[:,1],self.x[:,0]**3,np.ones(24)])
        q=np.r_[self.q,-self.q[1],self.q[0]**3,999]
        other=transport(x,q,self.y)
        np.testing.assert_allclose(original['atoms'],other['atoms'],atol=1e-12)
        self.assertEqual(original['coordinate_n'],other['coordinate_n'])
        perm=[3,0,5,2,1,4]
        np.testing.assert_allclose(other['atoms'],transport(x[:,perm],q[perm],self.y)['atoms'],atol=1e-12)

    def test_query_does_not_fit_preprocessing(self):
        a,_=design(self.x,self.q);b,_=design(self.x,self.q*100)
        # Canonical signs/order can depend on query only on exact train ties;
        # this independent nonduplicate fixture has identical training design.
        np.testing.assert_array_equal(a,b)
        self.assertTrue(np.allclose(a[:,1:].mean(axis=0),0))
        self.assertTrue(np.allclose(a[:,1:].std(axis=0),1))

    def test_invalid_input_and_label_affine_equivariance(self):
        with self.assertRaises(ValueError):transport(self.x[:23],self.q,self.y[:23])
        bad=self.x.copy();bad[0,0]=np.inf
        with self.assertRaises(ValueError):transport(bad,self.q,self.y)
        result=transport(self.x,self.q,self.y)
        shifted=transport(self.x,self.q,2*self.y+3)
        np.testing.assert_allclose(shifted['atoms'],2*np.array(result['atoms'])+3,atol=1e-12)

if __name__=='__main__':unittest.main()

class BoundaryTests(unittest.TestCase):
    def test_synthetic_common_support_and_all_models(self):
        from unittest.mock import patch
        from research import return_transport as m
        import pandas as pd
        rows=[];base=[]
        dates=pd.date_range('2014-01-31',periods=72,freq='ME')
        for i,date in enumerate(dates):
            outcomes={}
            for h,delay,first in [(12,0,24),(24,24,48)]:
                available=(date+pd.DateOffset(months=delay)+pd.Timedelta(days=1)).date().isoformat()
                target={'status':'complete','available':available,'values':[float(np.sin(i)),0.,0.],
                        'entry':date.date().isoformat(),'end':date.date().isoformat()}
                outcomes[str(h)]=target
                if i>=first:
                    base.append({'date':date.date().isoformat(),'horizon':h,'target':'terminal_log_return',
                        'role':'development','status':'scored','outcome':target['values'][0],
                        'entry':target['entry'],'end':target['end'],'label_available':available,
                        **{metric:1. for metric in m.METRICS}})
            rows.append({'date':date.date().isoformat(),'context':[i%7,float(np.cos(i))],'outcomes':outcomes})
        refs=[{'name':f'ref{i}'} for i in range(13)];arms=[{'name':f'arm{i}'} for i in range(6)]
        atlas={'atlas_id':'synthetic','models':[{'name':f'ref{i}','replica':None,'records':base} for i in range(15)]+[{'name':'generative','replica':i,'records':base} for i in (0,1)]}
        snapshot={'source_sha256':'synthetic','daily':[{'date':'2022-12-31'}]}
        with patch.object(m,'validate_atlas'),patch.object(m,'build_dataset',return_value={'rows':rows}),patch.object(m,'baseline_candidates',return_value=refs),patch.object(m,'validate_candidate',return_value=np.arange(72,dtype=float)):
            result=m.evaluate(snapshot,arms,{'name':'arm0','values':[0]*20+[1]*52},atlas)
            self.assertEqual(len(result['records']),23*72)
            self.assertEqual(len(result['cells']),23*2*17)
            self.assertEqual(len(result['matched_decoder_contrasts']),46)
            groups=result['availability_contributions']
            self.assertEqual(len(groups),23*2*2*3)
            for name in ['context+arm0','context+availability+attention']:
                for h in (12,24):
                    selected=[g for g in groups if g['model']==name and g['horizon']==h]
                    self.assertEqual(sum(g['n'] for g in selected),{12:48,24:24}[h])
                    overall=next(c for c in result['matched_decoder_contrasts'] if c['model']==name and c['horizon']==h)
                    self.assertAlmostEqual(sum(g['paired_gain_sum']['crps'] for g in selected),overall['reference_minus_model']['crps']*overall['n'])
            self.assertTrue(any(g['n'] and g['train_availability_group']=='mixed' for g in groups))
            for row in result['records']:
                self.assertEqual(len(row['train_dates']),24)
                self.assertTrue(all(d<row['date'] for d in row['train_dates']))
            atlas['models'][0]['records']=base[1:]
            with self.assertRaisesRegex(ValueError,'support'):m.evaluate(snapshot,arms,{'name':'arm0','values':[1]*72},atlas)

    def test_failed_registration_is_receipted_and_no_fit(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from research.return_transport_runner import run
        from research.scorecard_artifacts import verify_packet
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();reg=root/'reg.json';reg.write_text('{')
            with patch('research.return_transport.evaluate') as fit:
                with self.assertRaises(ValueError):run(reg,root/'out')
                fit.assert_not_called()
            receipt=verify_packet(root/'out')
            self.assertIn('registration.json',receipt['files'])
            self.assertIn('error.json',receipt['files'])
