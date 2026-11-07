import unittest
import numpy as np
import pandas as pd
from research.candidates.structural_state import generator as g

class StructuralStateTests(unittest.TestCase):
    def frame(self,returns):
        return pd.DataFrame({'Date':pd.date_range(end='2020-12-31',periods=len(returns)+1,freq='D'),'Price':100*np.exp(np.r_[0,np.cumsum(returns)])})
    def score(self,frame):return g.generate(frame,['2020-12-31']).iloc[-1,0]
    def test_independent_equal_gain_law(self):
        for count in (1,2,100,730):
            r=np.zeros(730);r[:count]=.001
            self.assertAlmostEqual(self.score(self.frame(r)),(730/count-1)/729,places=12)
        for r in (np.zeros(730),np.full(730,-.001)):
            result=g.generate(self.frame(r),['2020-12-31'])
            self.assertEqual(result.iloc[0,0],0.)
            self.assertEqual(result.iloc[0,1],'valid_no_upside_prior')
    def test_domain_gaps_stale_and_extremes(self):
        frame=self.frame(np.zeros(730))
        for bad in (frame.drop(index=12),frame.iloc[:-1],frame.iloc[1:]):
            self.assertEqual(self.score(bad),.5)
            self.assertEqual(g.generate(bad,['2020-12-31']).iloc[0,1],'neutral_missing_or_invalid_window')
        for value in (0.,-1.,np.inf,np.nan):
            bad=frame.copy();bad.loc[15,'Price']=value
            self.assertEqual(self.score(bad),.5)
        bad=frame.copy();bad.Price=np.resize([1e-300,1e300],len(frame))
        self.assertTrue(np.isfinite(self.score(bad)))
        for bad in (frame.iloc[::-1],pd.concat([frame,frame.tail(1)])):
            with self.assertRaises(ValueError):g.generate(bad)
    def test_scale_amplitude_and_gain_order_invariance(self):
        r=np.random.default_rng(811).normal(0,.01,730);frame=self.frame(r)
        baseline=self.score(frame)
        for amplitude in (.1,2.):self.assertAlmostEqual(self.score(self.frame(r*amplitude)),baseline,places=12)
        frame.Price*=37;self.assertAlmostEqual(self.score(frame),baseline,places=12)
        self.assertAlmostEqual(self.score(self.frame(r[::-1])),baseline,places=12)
        self.assertGreater(self.score(self.frame(np.r_[.73,np.zeros(729)])),baseline)
    def test_prefix_and_future_poisoning(self):
        frame=self.frame(np.random.default_rng(121).normal(0,.02,1100));original=g.generate(frame)
        for query in original.index[::3]:
            prefix=frame[frame.Date<=query]
            pd.testing.assert_frame_equal(g.generate(prefix),original.loc[:query])
            poisoned=frame.copy();future=poisoned.Date>query
            poisoned.loc[future,'Price']=np.geomspace(.01,1e8,future.sum())
            pd.testing.assert_frame_equal(g.generate(poisoned).loc[:query],original.loc[:query])
        self.assertTrue(original.iloc[:,0].between(0,1).all())
