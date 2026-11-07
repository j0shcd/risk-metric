"""Research-only self-financing policy probes; never an indicator selection gate.

Fixed capital 1, no contributions/cash yield/leverage, daily marked BTC/cash.
A monthly score is ranked against exactly 24 PRIOR monthly scores (midrank ties).
Two separate rules: continuous weight 1-percentile; 20/80 hysteresis initially
50%, switches to 100% at <=20% and 0% at >=80%, otherwise holds. Execution uses
next calendar day's supplied price; missing dates fail rather than shift orders.
Buyhold, cash and monthly 50/50 share the same eligible start and final mark.
Each probe also has an EX-POST constant-allocation comparator fitted to match
its realized calendar-time mean exposure; this is descriptive lookahead, not a
causal trading rule. No wealth winner, aggregate utility or market p-value.

CLI writes a new JSON file only; no browser, services, secrets or production.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


COST_BPS = (0.0, 25.0, 50.0)


def _series(values, name, *, positive=False, monthly=False):
    if not isinstance(values, pd.Series) or not isinstance(values.index, pd.DatetimeIndex):
        raise ValueError(f'{name} must be a dated Series')
    if (values.empty or values.index.has_duplicates or values.index.hasnans
            or values.index.tz is not None or not values.index.is_monotonic_increasing
            or not values.index.equals(values.index.normalize())):
        raise ValueError(f'{name} needs unique ordered naive calendar dates')
    values = values.astype(float)
    if not np.isfinite(values).all() or (positive and (values <= 0).any()):
        raise ValueError(f'{name} must be finite' + (' and positive' if positive else ''))
    expected = pd.date_range(values.index[0], values.index[-1], freq='ME' if monthly else 'D')
    if not values.index.equals(expected):
        raise ValueError(f'{name} requires complete ' + ('month ends' if monthly else 'daily prices'))
    return values


def trailing_percentile(scores):
    scores = _series(scores, 'scores', monthly=True)
    result = pd.Series(np.nan, index=scores.index, name='prior24_percentile')
    for i in range(24, len(scores)):
        previous, current = scores.iloc[i-24:i].to_numpy(), scores.iloc[i]
        result.iloc[i] = (np.sum(previous < current) + .5*np.sum(previous == current))/24
    return result


def policy_targets(scores):
    ranks = trailing_percentile(scores).dropna()
    continuous = 1-ranks
    hysteresis, weight = [], .5
    for rank in ranks:
        if rank <= .2:
            weight = 1.
        elif rank >= .8:
            weight = 0.
        hysteresis.append(weight)
    dates = ranks.index + pd.Timedelta(days=1)
    return {'continuous_contrarian': pd.Series(continuous.to_numpy(), index=dates),
            'hysteresis_20_80': pd.Series(hysteresis, index=dates, dtype=float)}


def simulate(prices, targets, cost_bps=25.0):
    """Targets are post-fee asset weights on execution dates; exact fee algebra."""
    prices = _series(prices, 'prices', positive=True)
    if (not isinstance(targets, pd.Series) or not isinstance(targets.index, pd.DatetimeIndex)
            or targets.empty or targets.index.has_duplicates or targets.index.hasnans
            or not targets.index.is_monotonic_increasing or targets.index.tz is not None
            or not targets.index.equals(targets.index.normalize())
            or not np.isfinite(targets).all() or not targets.between(0, 1).all()
            or not targets.index.isin(prices.index).all()):
        raise ValueError('targets must be finite weights [0,1] at unique available execution dates')
    if not np.isscalar(cost_bps) or not np.isfinite(cost_bps) or not 0 <= cost_bps < 10000:
        raise ValueError('cost_bps must be finite in [0,10000)')
    fee = cost_bps/10000
    prices = prices.loc[targets.index[0]:]
    cash, units, cumulative_fees, cumulative_turnover, cumulative_notional = 1., 0., 0., 0., 0.
    records = []
    for date, price in prices.items():
        asset = units*price
        before = cash+asset
        trade, costs, target = 0., 0., None
        if date in targets.index:
            target = float(targets.loc[date])
            delta = target*before-asset
            # Positive trade buys; negative trade sells. Target is a share of
            # POST-cost equity, so simply trading target*before is incorrect.
            trade = delta/(1+target*fee) if delta >= 0 else delta/(1-target*fee)
            costs = fee*abs(trade)
            cash -= trade+costs
            units += trade/price
            cumulative_fees += costs
            cumulative_notional += abs(trade)
            cumulative_turnover += abs(trade)/before
        if cash < -1e-12 or units < -1e-12 or cash+units*price <= 0:
            raise ValueError('self-financing long-only invariant violated')
        cash, units = max(cash, 0.), max(units, 0.)
        wealth = cash+units*price
        records.append({'date': date.date().isoformat(), 'price': float(price), 'cash': cash,
                        'units': units, 'wealth': wealth, 'exposure': units*price/wealth,
                        'target': target, 'trade_notional': trade, 'cost': costs})
    values = np.array([r['wealth'] for r in records])
    peaks = np.maximum.accumulate(np.r_[1., values])[1:]
    # Daily complete calendar: left-end allocation weights each elapsed day.
    exposure = float(np.mean([r['exposure'] for r in records[:-1]])) if len(records)>1 else records[0]['exposure']
    return {'initial_capital': 1., 'contributions': 0., 'cash_yield': 0., 'cost_bps_per_leg': float(cost_bps),
            'first_execution': records[0]['date'], 'final_mark': records[-1]['date'],
            'terminal_wealth': float(values[-1]), 'terminal_liquidatable_wealth': float(values[-1]-fee*units*prices.iloc[-1]),
            'max_drawdown': float(np.min(values/peaks-1)), 'realized_time_mean_exposure': exposure,
            'turnover_sum_fraction_pretrade_wealth': cumulative_turnover, 'traded_notional': cumulative_notional,
            'fees_paid': cumulative_fees, 'trade_count': sum(abs(r['trade_notional']) > 1e-14 for r in records),
            'terminal_liquidation_executed': False, 'ledger': records}


def matched_exposure(prices, execution_dates, probe, cost_bps):
    """Fit constant target to realized probe exposure using the complete path."""
    wanted = probe['realized_time_mean_exposure']
    lo, hi = 0., 1.
    result = None
    for _ in range(45):
        weight = (lo+hi)/2
        result = simulate(prices, pd.Series(weight, index=execution_dates), cost_bps)
        if result['realized_time_mean_exposure'] < wanted:
            lo = weight
        else:
            hi = weight
    if abs(result['realized_time_mean_exposure']-wanted) > 1e-10:
        raise ValueError('ex-post exposure matching did not converge')
    result.update({'ex_post_descriptive': True, 'matched_constant_target': weight,
                   'matched_probe_exposure': wanted,
                   'limitation': 'Fits realized future prices and probe exposure; not a causal comparator or matched pathwise risk'})
    return result


def run_probes(prices, scores, costs=COST_BPS):
    prices = _series(prices, 'prices', positive=True)
    scores = _series(scores, 'scores', monthly=True)
    targets = policy_targets(scores)
    all_dates = targets['continuous_contrarian'].index
    pending = all_dates[all_dates > prices.index[-1]]
    available = all_dates[all_dates <= prices.index[-1]]
    if not available.isin(prices.index).all():
        raise ValueError('an eligible next-calendar-day execution price is missing')
    costs = tuple(costs)
    if (not costs or len(set(costs)) != len(costs)
            or any(not np.isscalar(c) or not np.isfinite(c) or not 0 <= c < 10000 for c in costs)):
        raise ValueError('cost sensitivities must be nonempty, distinct and finite in [0,10000)')
    report = {'protocol': 'supporting-policy-probes-v1',
              'rules': {'rank': 'midrank against exactly 24 prior monthly scores',
                        'continuous': '1-percentile',
                        'hysteresis': 'initial 0.5; 1 at percentile<=0.2, 0 at percentile>=0.8, otherwise hold',
                        'execution': 'next calendar day supplied price',
                        'exposure': 'left-end daily post-trade asset weight across elapsed calendar days'},
              'status': 'eligible' if len(available) else 'insufficient_history_or_pending_execution',
              'first_eligible_decision': None if not len(available) else (available[0]-pd.Timedelta(days=1)).date().isoformat(),
              'first_execution': None if not len(available) else available[0].date().isoformat(),
              'final_mark': prices.index[-1].date().isoformat(), 'warmup_months': min(24,len(scores)),
              'pending_execution_dates': [d.date().isoformat() for d in pending], 'cost_cases': [],
              'limitations': ['Supporting descriptive policies, not a combined winner or indicator promotion gate.',
                             'No probability, market significance, investment suitability or future performance claim.',
                             'Cash yield zero; no taxes, funding, volume limits or market impact beyond stated per-leg fee.',
                             'Monthly scores assumed available at decision date; original source vintages remain caller responsibility.',
                             'Exposure matching is ex-post and does not match pathwise risk; no random-timing p-value.',
                             'Wealth/drawdown marked daily, no terminal liquidation; liquidatable wealth is a separate diagnostic.']}
    if not len(available):
        return report
    for cost in costs:
        rules = {name: target.loc[available] for name,target in targets.items()}
        rules.update({'buyhold': pd.Series(1.,index=available[:1]), 'cash':pd.Series(0.,index=available[:1]),
                      'constant_50_50': pd.Series(.5,index=available)})
        results = {name:simulate(prices, target, cost) for name,target in rules.items()}
        for name in targets:
            results['ex_post_exposure_matched_'+name] = matched_exposure(prices, available, results[name], cost)
        report['cost_cases'].append({'cost_bps_per_leg':float(cost),'policies':results})
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prices',type=Path,required=True,help='CSV Date,Price; complete daily dates')
    parser.add_argument('--scores',type=Path,required=True,help='CSV Date,score; complete month ends')
    parser.add_argument('--output',type=Path,required=True,help='New JSON file')
    args=parser.parse_args(argv)
    prices=pd.read_csv(args.prices,index_col='Date',parse_dates=True)['Price']
    scores=pd.read_csv(args.scores,index_col='Date',parse_dates=True)['score']
    result=run_probes(prices,scores)
    result['source_sha256'] = {name:hashlib.sha256(path.read_bytes()).hexdigest()
                              for name,path in [('prices',args.prices),('scores',args.scores),('producer',Path(__file__))]}
    with args.output.open('x') as handle:
        json.dump(result,handle,sort_keys=True,allow_nan=False); handle.write('\n')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
