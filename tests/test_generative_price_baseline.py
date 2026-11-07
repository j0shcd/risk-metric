import math
import unittest
from unittest.mock import patch
import numpy as np
from research import generative_price_baseline as g

class GenerativePriceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.returns=np.random.default_rng(1407).standard_t(5,730)*np.sqrt(3/5)*.03+.0002
        cls.posterior=g.fit(cls.returns)

    def test_filter_matches_scalar_normalized_t_density(self):
        values=np.array([.1,-.02,.04]);mu=.001;s=.03;h=s*s;expected=0.
        for value in values:
            expected+=(math.lgamma(3)-math.lgamma(2.5)-.5*math.log(3*math.pi*h)
                       -3*math.log1p((value-mu)**2/(3*h)))
            h=.01*s*s+.05*(value-mu)**2+.94*h
        actual,next_h=g.filter_log_likelihood(values,mu,s)
        self.assertAlmostEqual(float(actual),expected,places=12)
        self.assertAlmostEqual(float(next_h),h,places=14)
        vector,variance=g.filter_log_likelihood(values,np.array([mu,mu]),np.array([s,s]))
        np.testing.assert_allclose(vector,expected);np.testing.assert_allclose(variance,h)

    def test_posterior_matches_wider_finer_original_coordinate_reference(self):
        # Independent integration in original(mu,s), not(u,log s). No production
        # grid/filter helpers: this checks the Jacobian, density and state update.
        mus=np.linspace(-.012,.012,601);scales=np.linspace(.001,.20,601)
        mu,s=np.meshgrid(mus,scales,indexing='ij');h=s*s;log_density=np.zeros_like(h)
        for value in self.returns:
            error=value-mu
            log_density+=(math.lgamma(3)-math.lgamma(2.5)-.5*np.log(3*math.pi*h)
                          -3*np.log1p(error**2/(3*h)))
            h=.01*s*s+.05*error**2+.94*h
        log_density+=(.5*math.log(365/(2*math.pi))-np.log(s)-.5*365*(mu/s)**2
                      +.5*math.log(2/math.pi)-math.log(.05)-.5*(s/.05)**2)
        area=np.full(mu.shape,(mus[1]-mus[0])*(scales[1]-scales[0]))
        area[[0,-1],:]*=.5;area[:,[0,-1]]*=.5
        maximum=log_density.max();mass=np.exp(log_density-maximum)*area
        normalizer=mass.sum();mass/=normalizer
        ref_mean=float(np.sum(mass*mu));ref_var=float(np.sum(mass*(mu-ref_mean)**2))
        ref_scale=float(np.sum(mass*s*s));ref_h=float(np.sum(mass*h))
        p=self.posterior;d=p.diagnostics
        self.assertLess(abs(d['posterior_log_normalizer']-(maximum+np.log(normalizer))),1e-4)
        self.assertLess(abs(d['posterior_mean_mu']-ref_mean)/np.sqrt(ref_var),1e-3)
        for actual,expected in [(d['posterior_variance_mu'],ref_var),(d['posterior_mean_scale_squared'],ref_scale),(d['posterior_mean_next_variance'],ref_h)]:
            self.assertLess(abs(actual/expected-1),1e-3)
        self.assertAlmostEqual(p.weights.sum(),1.,places=12)
        self.assertGreater(d['posterior_variance_mu'],0.)
        self.assertFalse(p.mu.flags.writeable)

    def test_t_innovation_unit_variance_and_heavy_tails(self):
        z=np.random.default_rng(1408).standard_t(5,500000)*np.sqrt(3/5)
        self.assertLess(abs(np.var(z)-1),.025)
        self.assertGreater(np.mean(abs(z)>4),.001)
        self.assertAlmostEqual(.05**2*9+2*.05*.94+.94**2,1.0001)

    def test_parameter_uncertainty_has_h_squared_contribution(self):
        n=131072;mu=np.r_[np.full(n//2,-.001),np.full(n//2,.001)]
        days=[1,10,40]
        draws=g._simulate_draws(mu,np.full(n,.0001),np.full(n,.0001),days,np.random.default_rng(1409),alpha=0.,beta=1.)
        for i,h in enumerate(days):
            expected=h*.0001+h*h*.000001
            self.assertLess(abs(np.var(draws[:,i,0])/expected-1),.035)
        # A plug-in drift would omit more than a quarter of H=40 variance.
        self.assertGreater(np.var(draws[:,-1,0]),40*.0001*1.25)

    def test_entry_update_precedes_holding_variance(self):
        n=131072;days=[1,8];s2=.01;initial=1e-8
        draws=g._simulate_draws(np.zeros(n),np.full(n,s2),np.full(n,initial),days,np.random.default_rng(1410))
        for i,h in enumerate(days):
            expected=sum(s2+.99**k*(initial-s2) for k in range(1,h+1))
            self.assertLess(abs(np.var(draws[:,i,0])/expected-1),.04)

    def test_next_day_entry_and_true_drawdown(self):
        class FixedInnovations:
            def __init__(self):self.values=iter([99.,.2,-.5,.1])
            def standard_t(self,df,size):return np.full(size,next(self.values)/math.sqrt(3/5))
        values=g._simulate_draws(np.zeros(1),np.ones(1),np.ones(1),[1,2,3],FixedInnovations(),alpha=0.,beta=1.)
        np.testing.assert_allclose(values[0],[[.2,0,0],[-.3,.3,.5],[-.2,.3,.5]],atol=1e-14)

    def test_seed_reproducibility_horizon_prefix_and_mc_accuracy(self):
        p=self.posterior;days=[1,10,40]
        first=g.simulate(p,days,seed=1411);second=g.simulate(p,days,seed=1411)
        np.testing.assert_array_equal(first,second)
        self.assertEqual(first.shape,(8192,3,3))
        np.testing.assert_array_equal(first[:,:1],g.simulate(p,[1],seed=1411))
        np.testing.assert_array_equal(first[:,::-1],g.simulate(p,days[::-1],seed=1411))
        d=p.diagnostics;mu=d['posterior_mean_mu'];var_mu=d['posterior_variance_mu']
        s2=d['posterior_mean_scale_squared'];h0=d['posterior_mean_next_variance']
        for i,h in enumerate(days):
            expected=sum(s2+.99**k*(h0-s2) for k in range(1,h+1))+h*h*var_mu
            self.assertLess(abs(first[:,i,0].mean()-h*mu),6*np.sqrt(expected/8192))
            self.assertLess(abs(first[:,i,0].var()/expected-1),.15)

    def test_adding_four_year_horizon_preserves_shorter_paths(self):
        short=g.simulate(self.posterior,[365,730],seed=1412)
        long=g.simulate(self.posterior,[365,730,1461],seed=1412)
        np.testing.assert_array_equal(short,long[:,:2])

    def test_exact_window_determinism_and_visible_failures(self):
        original=self.returns.copy();other=g.fit(self.returns.copy())
        for name in ['mu','scale','next_variance','weights']:
            np.testing.assert_array_equal(getattr(other,name),getattr(self.posterior,name))
        np.testing.assert_array_equal(self.returns,original)
        for invalid in [self.returns[:-1],np.r_[self.returns,99.],np.full(730,np.nan),np.zeros(730)]:
            with self.assertRaises(g.FitError):g.fit(invalid)
        bad={key:1. for key in g.PROTOCOL['tolerances']}
        with patch.object(g,'_convergence',return_value=bad):
            with self.assertRaisesRegex(g.FitError,'did not converge'):g.fit(self.returns)
        with self.assertRaises(ValueError):g.simulate(self.posterior,[0],seed=1)

if __name__=='__main__':unittest.main()
