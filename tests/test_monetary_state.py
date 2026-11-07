from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from research.candidates.monetary_state import generate as m


def source(end='2022-12-31'):
    dates=pd.date_range('2010-01-01',end,freq='D')
    return pd.DataFrame({'Date':dates,'real_yield_10y':np.arange(len(dates))/365})


class MonetaryStateTests(unittest.TestCase):
    def test_direction_units_and_fixed_scale(self):
        data=source();origin=pd.DatetimeIndex(['2020-01-31'])
        row=m.generate(data,origin).iloc[0]
        self.assertEqual(row['cutoff'],'2019-12-17');self.assertEqual(row['prior_anchor'],'2018-12-17')
        self.assertAlmostEqual(row['change_pp'],1)
        self.assertAlmostEqual(row['monetary_risk'],50+50*np.tanh(1))
        data['real_yield_10y']=-data['real_yield_10y']
        self.assertAlmostEqual(m.generate(data,origin).iloc[0]['monetary_risk'],50-50*np.tanh(1))
        data['real_yield_10y']=2
        self.assertEqual(m.generate(data,origin).iloc[0]['monetary_risk'],50)

    def test_prefix_future_shock_and_lagged_input_exclusion(self):
        data=source();origins=pd.date_range('2014-12-31','2022-12-31',freq='ME')
        full=m.generate(data,origins)
        for count in (1,12,24,48,64,65,66,72,96,97):
            date=origins[count-1];prefix=data[data.Date<=date]
            pd.testing.assert_frame_equal(m.generate(prefix,origins[:count]),full.iloc[:count].reset_index(drop=True))
        date=pd.Timestamp('2020-01-31');cutoff=date-pd.Timedelta(days=45)
        shocked=data.copy();shocked.loc[shocked.Date>cutoff,'real_yield_10y']=10000
        pd.testing.assert_frame_equal(m.generate(data,[date]),m.generate(shocked,[date]))
        truncated=data[data.Date<=cutoff]
        pd.testing.assert_frame_equal(m.generate(data,[date]),m.generate(truncated,[date]))
        # Irrelevant future price/outcome columns are never consulted.
        shocked['btc_future_return']=np.arange(len(shocked))*999
        pd.testing.assert_frame_equal(m.generate(data,[date]),m.generate(shocked,[date]))

    def test_missing_stale_and_calendar_boundaries(self):
        origin=pd.DatetimeIndex(['2020-04-30']);row=m.generate(source(),origin).iloc[0]
        self.assertEqual(row['cutoff'],'2020-03-16');self.assertEqual(row['prior_anchor'],'2019-03-16')
        empty=source().iloc[:0];result=m.generate(empty,origin)
        self.assertEqual(result.iloc[0]['status'],'neutral_missing_endpoint');self.assertEqual(result.iloc[0]['monetary_risk'],50)
        data=source();data.loc[data.Date>'2020-02-29','real_yield_10y']=np.nan
        result=m.generate(data,origin);self.assertEqual(result.iloc[0]['status'],'neutral_stale_endpoint');self.assertEqual(result.iloc[0]['monetary_risk'],50)
        for age,status in ((14,'observed'),(15,'neutral_stale_endpoint')):
            data=source();data.loc[data.Date>pd.Timestamp('2020-03-16')-pd.Timedelta(days=age),'real_yield_10y']=np.nan
            self.assertEqual(m.generate(data,origin).iloc[0]['status'],status)

    def test_domain_fail_closed_and_extreme_finite_values(self):
        origin=pd.DatetimeIndex(['2020-01-31']);data=source()
        for invalid in (pd.concat([data,data.iloc[-1:]]),data.iloc[::-1],data.assign(real_yield_10y=np.inf),data.assign(real_yield_10y='not a number')):
            with self.assertRaises(ValueError):m.generate(invalid,origin)
        for origins in (['2020-01-30'],['2020-01-31','2020-01-31'],['2020-01-31T00:00:00Z']):
            with self.assertRaises(ValueError):m.generate(data,origins)
        data['real_yield_10y']=data['real_yield_10y']*1e9
        score=m.generate(data,origin).iloc[0]['monetary_risk'];self.assertTrue(np.isfinite(score));self.assertTrue(0<=score<=100)

    def test_cli_macro_only_all97_exclusive_and_config_frozen(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);bundle=root/'bundle';bundle.mkdir()
            raw=source().to_csv(index=False).encode();(bundle/m.CONFIG['source_file']).write_bytes(raw)
            (bundle/'manifest.json').write_text(json.dumps({'cutoff':'2022-12-31','sources':{m.CONFIG['source_file']:{'development_sha256':m.sha(raw)}}}))
            output=root/'output';args=['--bundle',str(bundle),'--output-dir',str(output)]
            with redirect_stdout(io.StringIO()):m.main(args)
            result=pd.read_csv(output/'candidate.csv');self.assertEqual(len(result),97);self.assertTrue(np.isfinite(result.monetary_risk).all())
            self.assertEqual(result.Date.iloc[0],'2014-12-31');self.assertEqual(result.Date.iloc[-1],'2022-12-31')
            with self.assertRaises(FileExistsError):m.main(args)
            changed=deepcopy(m.CONFIG);changed['lag_calendar_days']=0;config=root/'bad.json';config.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError,'fixed specification'):m.main(args+['--config',str(config)])
            (bundle/m.CONFIG['source_file']).write_text('changed')
            with self.assertRaisesRegex(ValueError,'hash/cutoff'):m.main(args)

if __name__=='__main__':unittest.main()
