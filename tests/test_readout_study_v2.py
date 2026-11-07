import unittest
from unittest.mock import patch
import numpy as np
from research import readout_study as v1
from research import readout_study_v2 as v2
from research.distribution_readout import weighted_crps

class DuplicateInvariantOracle(unittest.TestCase):
    def setUp(self):
        x=np.arange(24,dtype=float)
        self.train=np.c_[x,(7*x)%24]
        self.query=np.array([0.,0.])

    def test_no_information_duplicate_oracle(self):
        base,_=v2.decode(self.train,self.query,'rank')
        for coordinate in [0,1]:
            augmented=np.c_[self.train,self.train[:,coordinate]]
            query=np.r_[self.query,self.query[coordinate]]
            weights,info=v2.decode(augmented,query,'rank')
            np.testing.assert_array_equal(weights,base)
            self.assertEqual(info['rank_coordinate_classes'],2)
            self.assertEqual(weighted_crps(np.arange(24.),weights,0.),weighted_crps(np.arange(24.),base,0.))
        # This fixture must expose the original defect, otherwise the oracle is weak.
        old,_=v1.decode(np.c_[self.train,self.train[:,0]],np.r_[self.query,0.],'rank')
        self.assertGreater(np.max(abs(old-base)),.01)

    def test_monotone_multiple_duplicates_and_column_permutation(self):
        base,_=v2.decode(self.train,self.query,'rank')
        augmented=np.c_[self.train,np.exp(self.train[:,0]),self.train[:,1]**3,self.train[:,0]]
        query=np.r_[self.query,1.,0.,0.]
        for order in [np.arange(5),np.array([4,2,0,3,1]),np.arange(4,-1,-1)]:
            weights,info=v2.decode(augmented[:,order],query[order],'rank')
            np.testing.assert_array_equal(weights,base)
            self.assertEqual(info['rank_coordinate_classes'],2)

    def test_query_breaks_training_equivalence(self):
        x=np.arange(24,dtype=float)
        ranks,q=v1.percentile(np.c_[x,x],np.array([5.,20.]))
        deduplicated,query=v2.canonical_rank_coordinates(ranks,q)
        self.assertEqual(deduplicated.shape,(24,2))
        self.assertNotEqual(query[0],query[1])

    def test_fractional_tie_mass_is_eight(self):
        x=np.r_[np.zeros(6),np.ones(6),np.full(12,2.)]
        weights,info=v2.decode(np.c_[x,x],np.array([0.,0.]),'rank')
        membership=(weights-1/48)*16
        np.testing.assert_allclose(membership[:6],1.)
        np.testing.assert_allclose(membership[6:12],1/3)
        np.testing.assert_allclose(membership[12:],0.)
        self.assertAlmostEqual(membership.sum(),8.)
        self.assertAlmostEqual(info['local_mass'],8.)

    def test_evaluation_restores_original_decoder_on_error(self):
        original=v1.decode
        with self.assertRaises(ValueError):
            v2.evaluate({'daily':[{'date':'2023-01-01'}]},[])
        self.assertIs(v1.decode,original)

if __name__=='__main__': unittest.main()
