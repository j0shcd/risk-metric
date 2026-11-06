import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from research.policy_probes import main, matched_exposure, policy_targets, run_probes, simulate, trailing_percentile


class PolicyProbeTests(unittest.TestCase):
    def setUp(self):
        self.dates=pd.date_range('2000-01-31',periods=28,freq='ME')
        self.scores=pd.Series(np.arange(28,dtype=float),index=self.dates)
        self.prices=pd.Series(10.,index=pd.date_range('2000-01-01','2002-05-02'))

    def test_prior24_excludes_current_and_ties_are_midrank(self):
        ranks=trailing_percentile(self.scores)
        self.assertTrue(ranks.iloc[:24].isna().all())
        self.assertEqual(ranks.iloc[24],1.)
        self.assertEqual(trailing_percentile(self.scores*0).iloc[24],.5)
        descending=-self.scores
        self.assertEqual(trailing_percentile(descending).iloc[24],0.)

    def test_rank_window_is_exactly24_not_expanding(self):
        scores=self.scores.copy()
        scores.iloc[0]=1e9
        scores.iloc[25]=24.5
        self.assertEqual(trailing_percentile(scores).iloc[25],1.)

    def test_hysteresis_and_execution_lag(self):
        scores=pd.Series(0.,index=pd.date_range('2000-01-31',periods=29,freq='ME'))
        scores.iloc[25:]=[-10,0,10,0]
        targets=policy_targets(scores)
        self.assertEqual(targets['hysteresis_20_80'].tolist(),[.5,1.,1.,0.,0.])
        self.assertEqual(targets['hysteresis_20_80'].index[0],pd.Timestamp('2002-02-01'))

    def test_prefix_causality_for_targets_and_executed_ledger(self):
        self.scores.iloc[24:]=[-3,27,0,26]
        full=policy_targets(self.scores)
        prefix=policy_targets(self.scores.iloc[:26])
        changed=self.scores.copy();changed.iloc[26:]=1e10
        for name in full:
            pd.testing.assert_series_equal(full[name].loc[prefix[name].index],prefix[name])
            pd.testing.assert_series_equal(full[name].loc[prefix[name].index],policy_targets(changed)[name].loc[prefix[name].index])
        date=pd.Timestamp('2002-03-15')
        prices=self.prices.copy();prices.loc[date:]=np.linspace(10,30,len(prices.loc[date:]))
        target=full['continuous_contrarian']
        a=simulate(prices,target,25)
        b=simulate(prices.loc[:date],target.loc[:date],25)
        self.assertEqual(a['ledger'][:len(b['ledger'])],b['ledger'])

    def test_self_financing_exact_postcost_weight_and_price_units(self):
        dates=pd.date_range('2000-01-01',periods=4)
        prices=pd.Series([2.,3.,1.,4.],index=dates)
        target=pd.Series([1.,.5,0.,.8],index=dates)
        result=simulate(prices,target,25)
        previous_cash,previous_units=1.,0.
        for row in result['ledger']:
            before=previous_cash+previous_units*row['price']
            self.assertAlmostEqual(row['cash'],previous_cash-row['trade_notional']-row['cost'])
            self.assertAlmostEqual(row['units'],previous_units+row['trade_notional']/row['price'])
            self.assertAlmostEqual(row['wealth'],before-row['cost'])
            self.assertAlmostEqual(row['exposure'],row['target'])
            self.assertGreaterEqual(row['cash'],0.)
            self.assertGreaterEqual(row['units'],0.)
            previous_cash,previous_units=row['cash'],row['units']
        scaled=simulate(prices*1000,target,25)
        self.assertAlmostEqual(result['terminal_wealth'],scaled['terminal_wealth'])
        for first,second in zip(result['ledger'],scaled['ledger']):
            self.assertAlmostEqual(first['units']/1000,second['units'])

    def test_buyhold_cash_and_initial_cost_drawdown(self):
        dates=pd.date_range('2000-01-01',periods=3)
        prices=pd.Series([10.,20.,10.],index=dates)
        buy=simulate(prices,pd.Series(1.,index=dates[:1]),25)
        self.assertAlmostEqual(buy['ledger'][0]['units'],1/(10*1.0025))
        self.assertAlmostEqual(buy['terminal_wealth'],1/1.0025)
        self.assertAlmostEqual(buy['terminal_liquidatable_wealth'],.9975/1.0025)
        self.assertEqual(buy['max_drawdown'],-.5)
        cash=simulate(prices,pd.Series(0.,index=dates[:1]),50)
        self.assertEqual(cash['terminal_wealth'],1.)
        self.assertEqual(cash['fees_paid'],0.)
        initial=simulate(pd.Series(10.,index=dates),pd.Series(1.,index=dates[:1]),25)
        self.assertAlmostEqual(initial['max_drawdown'],1/1.0025-1)

    def test_flat_price_cost_monotonicity_and_no_capital_creation(self):
        dates=pd.date_range('2000-01-01',periods=6)
        prices=pd.Series(7.,index=dates)
        target=pd.Series([1.,0.,.5,1.,0.,.5],index=dates)
        wealth=[simulate(prices,target,c)['terminal_wealth'] for c in (0,25,50)]
        self.assertAlmostEqual(wealth[0],1.)
        self.assertGreater(wealth[0],wealth[1]);self.assertGreater(wealth[1],wealth[2])

    def test_report_common_capital_support_and_expost_exposure(self):
        # Three months with nontrivial changes, enough to exercise matching.
        prices=self.prices.loc[:'2002-04-03'].copy()
        prices.loc['2002-02-01':]=np.linspace(10,17,len(prices.loc['2002-02-01':]))
        scores=self.scores.copy();scores.iloc[24:]=[-3,27,0,26]
        report=run_probes(prices,scores,costs=(25,))
        self.assertEqual(report['first_execution'],'2002-02-01')
        self.assertEqual(report['pending_execution_dates'],['2002-05-01'])
        results=report['cost_cases'][0]['policies']
        for result in results.values():
            self.assertEqual(result['initial_capital'],1.)
            self.assertEqual(result['contributions'],0.)
            self.assertEqual(result['first_execution'],'2002-02-01')
            self.assertEqual(result['final_mark'],'2002-04-03')
        for name in ('continuous_contrarian','hysteresis_20_80'):
            matched=results['ex_post_exposure_matched_'+name]
            self.assertTrue(matched['ex_post_descriptive'])
            self.assertAlmostEqual(matched['realized_time_mean_exposure'],results[name]['realized_time_mean_exposure'],places=10)

    def test_missing_execution_or_history_fails_and_pending_is_explicit(self):
        with self.assertRaises(ValueError):
            run_probes(self.prices.drop(pd.Timestamp('2002-02-01')),self.scores)
        with self.assertRaises(ValueError):
            policy_targets(self.scores.drop(self.scores.index[3]))
        report=run_probes(self.prices,self.scores.iloc[:24])
        self.assertEqual(report['status'],'insufficient_history_or_pending_execution')
        self.assertFalse(report['cost_cases'])
        report=run_probes(self.prices.loc[:'2002-01-31'],self.scores.iloc[:25])
        self.assertEqual(report['pending_execution_dates'],['2002-02-01'])
        self.assertFalse(report['cost_cases'])

    def test_invalid_costs_fail_even_without_eligible_history(self):
        for costs in ((), (25,25), (float("nan"),), (-1,), (10000,)):
            with self.assertRaises(ValueError):
                run_probes(self.prices,self.scores.iloc[:24],costs=costs)

    def test_cli_synthetic_e2e_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.prices.loc[:'2002-02-03'].rename_axis('Date').rename('Price').to_csv(root/'prices.csv')
            self.scores.iloc[:25].rename_axis('Date').rename('score').to_csv(root/'scores.csv')
            args=['--prices',str(root/'prices.csv'),'--scores',str(root/'scores.csv'),'--output',str(root/'out.json')]
            self.assertEqual(main(args),0)
            report=json.loads((root/'out.json').read_text())
            self.assertEqual([c['cost_bps_per_leg'] for c in report['cost_cases']],[0.,25.,50.])
            with self.assertRaises(FileExistsError):main(args)


if __name__=='__main__':
    unittest.main()
