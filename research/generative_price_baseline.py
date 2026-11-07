"""Frozen price-only Student-t volatility baseline; no market fitting at import.

fit() accepts exactly 730 past daily log returns. Its posterior is a deterministic
finite-domain quadrature approximation, not a point estimate or exact posterior.
Convergence and edge diagnostics are numerical proxies, not proven bounds on
excluded posterior mass. FitError is a visible unavailable forecast; never fall
back silently. Priors, domain and grids are fixed before any market evaluation.

simulate() returns [8192 paths, requested horizons, 3 targets] in log units. The
first generated return establishes next-day entry and updates volatility; only
subsequent holding returns enter terminal return and daily-close downside paths.
One posterior parameter draw is held for the entire path. All horizons reuse the
same path. Student-t log returns have no finite positive exponential moments:
do not interpret simulated mean prices/wealth as model expectations. The fixed
t5/GARCH recursion has a finite stationary second moment but no stationary fourth
moment: .05^2*E[z^4]+2*.05*.94+.94^2 = 1.0001. Finite-horizon simulation
remains defined;8192paths do not imply precise extreme-tail or variance estimates.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
from typing import Sequence
import numpy as np

PATHS = 8192
WINDOW = 730
DF = 5
ALPHA = .05
BETA = .94
PROTOCOL = {
    'id':'student-t5-price-path-v1','window_daily_log_returns':WINDOW,'paths':PATHS,
    'model':'r=mu+sqrt(h)*sqrt(3/5)*t5; h_next=.01*s^2+.05*(r-mu)^2+.94*h',
    'initial_history_variance':'s^2 at start of trailing730-return window',
    'priors':{'scale_halfnormal_sd':.05,'mu_given_scale_variance':'s^2/365'},
    'posterior_coordinates':'u=mu/s, y=log(s); prior includes Jacobian exp(y)',
    'outer_domain':{'u':[-.5,.5],'scale':[1e-5,.5]},
    'quadrature':'tensor trapezoid;65^2 coarse; marginal1e-8 tails+4coarse-cell padding;local65,129,257 meshes',
    'tolerances':{'density_interpolation_l1':.005,'log_normalizer_change':1e-4,
                  'scaled_moment_change':1e-3,'edge_strip_mass':1e-6},
    'edge_strip':'outer2% of each coordinate interval; numerical proxy, not excluded-tail bound',
    'entry':'first innovation is next-day entry; then requested integer holding days',
    'targets':['terminal_log_return','entry_adverse_log_loss','peak_drawdown_log_loss'],
    'parameter_uncertainty':'one joint(mu,s,h_next) draw per path, held across all days/horizons',
    'failure':'FitError; no plug-in or pooled fallback',
    'fourth_moment':'stationary fourth moment not finite: .05^2*9+2*.05*.94+.94^2=1.0001',
    'interpretation':'price-only model-based reconstruction, not calibrated or production-qualified',
}

class FitError(ValueError):
    """The fixed posterior approximation could not produce a qualified forecast."""

@dataclass(frozen=True)
class Posterior:
    mu: np.ndarray
    scale: np.ndarray
    next_variance: np.ndarray
    weights: np.ndarray
    diagnostics: dict


def filter_log_likelihood(log_returns, mu, scale):
    """Likelihood and next-day conditional variance; vectorized over parameters.

    Each current return is scored at the PRE-update variance. The returned
    variance includes the update for the final observed return.
    """
    returns = np.asarray(log_returns, dtype=float)
    mu, scale = np.broadcast_arrays(np.asarray(mu, float), np.asarray(scale, float))
    if (returns.ndim != 1 or not np.isfinite(returns).all() or not np.isfinite(mu).all()
            or not np.isfinite(scale).all() or (scale <= 0).any()):
        raise ValueError('finite returns and drift, positive finite scale required')
    g = np.ones_like(scale)
    likelihood = np.zeros_like(scale)
    u = mu / scale
    constant = math.lgamma(3.)-math.lgamma(2.5)-.5*math.log(3.*math.pi)
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        for value in returns:
            error = value / scale - u
            likelihood += constant - np.log(scale) - .5*np.log(g) - 3.*np.log1p(error**2/(3.*g))
            g = .01 + ALPHA*error**2 + BETA*g
        return likelihood, scale**2*g


def _trapezoid(axis):
    weights = np.full(len(axis), (axis[-1]-axis[0])/(len(axis)-1))
    weights[[0,-1]] *= .5
    return weights


def _grid(returns, u_bounds, y_bounds, count):
    u_axis, y_axis = np.linspace(*u_bounds,count), np.linspace(*y_bounds,count)
    u,y = np.meshgrid(u_axis,y_axis,indexing='ij')
    scale=np.exp(y);mu=u*scale
    likelihood,next_variance=filter_log_likelihood(returns,mu,scale)
    log_prior = (.5*math.log(365./(2*math.pi)) - .5*365.*u**2
                 + .5*math.log(2/math.pi)-math.log(.05)-.5*(scale/.05)**2+y)
    log_density=likelihood+log_prior
    maximum=float(np.max(log_density))
    density=np.exp(log_density-maximum)
    area=_trapezoid(u_axis)[:,None]*_trapezoid(y_axis)[None,:]
    normalizer=float(np.sum(density*area))
    if not np.isfinite(normalizer) or normalizer<=0:raise FitError('nonfinite posterior normalizer')
    density/=normalizer;weights=density*area
    edge_u=(u_axis<=u_axis[0]+.02*np.ptp(u_axis)) | (u_axis>=u_axis[-1]-.02*np.ptp(u_axis))
    edge_y=(y_axis<=y_axis[0]+.02*np.ptp(y_axis)) | (y_axis>=y_axis[-1]-.02*np.ptp(y_axis))
    edge=float(weights[edge_u[:,None]|edge_y[None,:]].sum())
    mean_mu=float(np.sum(weights*mu))
    moments=np.array([mean_mu,float(np.sum(weights*(mu-mean_mu)**2)),
                      float(np.sum(weights*scale**2)),float(np.sum(weights*next_variance))])
    return {'u':u_axis,'y':y_axis,'mu':mu,'scale':scale,'next_variance':next_variance,
            'density':density,'weights':weights,'area':area,'log_normalizer':maximum+math.log(normalizer),
            'edge_mass':edge,'moments':moments}


def _local_bounds(grid):
    bounds=[]
    for name,axis in [('u',1),('y',0)]:
        cdf=np.cumsum(grid['weights'].sum(axis=axis))
        lower=max(0,int(np.searchsorted(cdf,1e-8))-4)
        upper=min(len(cdf)-1,int(np.searchsorted(cdf,1-1e-8))+4)
        if upper-lower<8:raise FitError('posterior localization collapsed')
        bounds.append((float(grid[name][lower]),float(grid[name][upper])))
    return bounds


def _convergence(previous,current):
    y_interpolated=np.array([np.interp(current['y'],previous['y'],row) for row in previous['density']])
    interpolated=np.array([np.interp(current['u'],previous['u'],column) for column in y_interpolated.T]).T
    density_l1=float(np.sum(abs(current['density']-interpolated)*current['area']))
    a,b=previous['moments'],current['moments']
    denominators=np.array([max(math.sqrt(b[1]),1e-12),max(b[1],1e-24),max(b[2],1e-24),max(b[3],1e-24)])
    return {'density_interpolation_l1':density_l1,
            'log_normalizer_change':abs(current['log_normalizer']-previous['log_normalizer']),
            'scaled_moment_change':float(np.max(abs(a-b)/denominators)),
            'componentwise_scaled_moment_change':(abs(a-b)/denominators).tolist(),
            'edge_strip_mass':current['edge_mass']}


def fit(log_returns):
    """Fit the fixed two-parameter model using past returns only; no RNG or labels."""
    returns=np.asarray(log_returns,dtype=float)
    if returns.shape!=(WINDOW,) or not np.isfinite(returns).all():
        raise FitError('fit requires exactly730 finite past daily log returns')
    try:
        coarse=_grid(returns,(-.5,.5),(math.log(1e-5),math.log(.5)),65)
        if coarse['edge_mass']>1e-6:raise FitError('posterior reaches fixed outer domain boundary')
        u_bounds,y_bounds=_local_bounds(coarse)
        previous=_grid(returns,u_bounds,y_bounds,65)
        trace=[];accepted=None
        for count in (129,257):
            current=_grid(returns,u_bounds,y_bounds,count)
            check=_convergence(previous,current)
            trace.append({'grid_count':count,**check})
            if all(check[key]<=limit for key,limit in PROTOCOL['tolerances'].items()):
                accepted=current;break
            previous=current
        if accepted is None:raise FitError('posterior mesh did not converge: '+repr(trace))
    except (FloatingPointError,OverflowError) as error:
        raise FitError('nonfinite fixed-domain likelihood: '+str(error)) from error
    diagnostics={'converged':True,'method':'finite-domain deterministic trapezoidal approximation',
                 'window':WINDOW,'grid_count':count,'u_bounds':list(u_bounds),'log_scale_bounds':list(y_bounds),
                 'outer_edge_strip_mass':coarse['edge_mass'],'convergence_trace':trace,
                 'posterior_log_normalizer':accepted['log_normalizer'],
                 'moment_normalization':['mean_mu / posterior_sd_mu','variance_mu / itself','mean_scale_squared / itself','mean_next_variance / itself'],
                 'posterior_mean_mu':float(accepted['moments'][0]),'posterior_variance_mu':float(accepted['moments'][1]),
                 'posterior_mean_scale_squared':float(accepted['moments'][2]),
                 'posterior_mean_next_variance':float(accepted['moments'][3]),
                 'error_scope':'mesh/edge proxies only; no rigorous excluded-tail or misspecification guarantee'}
    arrays=[]
    for name in ['mu','scale','next_variance','weights']:
        value=accepted[name].ravel().copy();value.setflags(write=False);arrays.append(value)
    return Posterior(*arrays,diagnostics)


def _holding_days(holding_days):
    days=list(holding_days)
    if (not days or any(type(d) is not int or d<1 or d>366*5 for d in days)
            or len(set(days))!=len(days)):
        raise ValueError('distinct integer holding horizons1..1830 days required')
    return days


def _simulate_draws(mu, scale_squared, next_variance, holding_days, rng, *, alpha=ALPHA,beta=BETA):
    """Simulation kernel; dynamics overrides exist only for synthetic invariants."""
    days=_holding_days(holding_days);locations={day:i for i,day in enumerate(days)}
    mu=np.asarray(mu,float);variance=np.asarray(next_variance,float).copy()
    n=len(mu);outcomes=np.empty((n,len(days),3))
    log_value=np.zeros(n);minimum=np.zeros(n);peak=np.zeros(n);drawdown=np.zeros(n)
    for step in range(max(days)+1):
        shock=np.sqrt(variance)*rng.standard_t(DF,size=n)*math.sqrt(3/5)
        increment=mu+shock
        variance=(1-alpha-beta)*scale_squared+alpha*shock**2+beta*variance
        if step==0:continue  # Entry return affects volatility, not holding outcomes.
        log_value+=increment;minimum=np.minimum(minimum,log_value)
        peak=np.maximum(peak,log_value);drawdown=np.maximum(drawdown,peak-log_value)
        if step in locations:
            outcomes[:,locations[step],:]=np.column_stack([log_value,-minimum,drawdown])
    if not np.isfinite(outcomes).all():raise FitError('nonfinite simulated log outcomes')
    return outcomes


def simulate(posterior: Posterior, holding_days: Sequence[int], *, seed: int):
    """Return fixed8192 posterior predictive log-outcome paths in requested order."""
    days=_holding_days(holding_days)
    if type(seed) is not int or seed<0:raise ValueError('nonnegative integer seed required')
    arrays=[np.asarray(getattr(posterior,name),float) for name in ['mu','scale','next_variance','weights']]
    mu,scale,variance,weights=arrays
    if (not posterior.diagnostics.get('converged') or mu.ndim!=1 or not len(mu)
            or any(a.shape!=mu.shape or not np.isfinite(a).all() for a in arrays)
            or (scale<=0).any() or (variance<=0).any() or (weights<0).any()
            or not np.isclose(weights.sum(),1.,rtol=0,atol=1e-10)):
        raise FitError('qualified finite posterior required')
    rng=np.random.default_rng(seed)
    selection=rng.choice(len(weights),size=PATHS,p=weights/weights.sum())
    return _simulate_draws(mu[selection],scale[selection]**2,variance[selection],days,rng)
