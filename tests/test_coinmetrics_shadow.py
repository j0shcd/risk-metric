"""All prices/responses invented locally; never contacts a provider."""
import base64
import io
import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib import parse
import numpy as np
import pandas as pd
from research import coinmetrics_shadow as c
from research.shadow_capture import capture_response, verify_capture, CaptureFailure
from research.distribution_readout import weighted_crps


def url(day,token=None):
    params=c._parameters(day)
    if token:params['next_page_token']=token
    return 'https://'+c.HOST+c.PATH+'?'+parse.urlencode(params)


def envelope(day, rows, extra=None):
    body={'data':rows}
    if extra:body.update(extra)
    payload=c.canonical_bytes(body)
    return c.canonical_bytes({'schema':'coinmetrics-exact-pages-v1','query_day':day,'complete':True,
        'pages':[0],'responses':[{'url':url(day),'status':200,'body_complete':True,
        'body_base64':base64.b64encode(payload).decode()}],'errors':[]})


def synthetic(day='2024-02-28'):
    dates=pd.date_range('2017-01-01',pd.Timestamp(day)-pd.Timedelta(days=1),freq='D')
    r=np.random.default_rng(1407).standard_t(5,len(dates))*np.sqrt(3/5)*.03+.0002
    # Known convergent trailing window from the unchanged baseline's own test.
    r[-730:]=np.random.default_rng(1407).standard_t(5,730)*np.sqrt(3/5)*.03+.0002
    prices=np.exp(5+np.cumsum(r))
    rows=[{'asset':'btc','time':d.strftime('%Y-%m-%dT00:00:00Z'),'PriceUSD':str(p)} for d,p in zip(dates,prices)]
    return rows


class Response(io.BytesIO):
    def __init__(self,body,status=200,headers=None):
        super().__init__(body);self.status=status;self.headers=headers or {}

class Opener:
    def __init__(self,responses):self.responses=iter(responses);self.calls=[]
    def open(self,request,timeout):
        self.calls.append((request,timeout));value=next(self.responses)
        if isinstance(value,Exception):raise value
        return value

class Clock:
    value=0.
    def monotonic(self):return self.value
    def sleep(self,seconds):self.value+=seconds


class CollectorTests(unittest.TestCase):
    def collect(self,responses):
        day=datetime.now(timezone.utc).date().isoformat();opener=Opener(responses);clock=Clock();saved=[]
        with patch.object(c.request,'build_opener',return_value=opener),patch.object(c.time,'monotonic',clock.monotonic),patch.object(c.time,'sleep',clock.sleep):
            result=c._collect({'query_day':day},saved.append)
        return result,opener,clock,saved

    def test_pagination_rate_and_exact_owned_bytes(self):
        day=datetime.now(timezone.utc).date().isoformat();next_url=url(day,'abc')
        first=c.canonical_bytes({'data':[{'PriceUSD':'not parsed in collector'}],'next_page_token':'abc','next_page_url':next_url})
        second=b'{"data": []}'
        (raw,meta),opener,clock,saved=self.collect([Response(first),Response(second)])
        state=json.loads(raw);self.assertTrue(state['complete']);self.assertEqual(meta['requests'],2)
        self.assertEqual(clock.value,2.);self.assertEqual(len(saved)>3,True)
        self.assertEqual([base64.b64decode(p['body_base64']) for p in state['responses']],[first,second])
        self.assertEqual(opener.calls[1][0].full_url,next_url)
        self.assertTrue(all(t<=10 for _,t in opener.calls))

    def test_response_metadata_allowlist_and_every_attempt(self):
        headers={'Date':'Sat, 07 Nov 2026 12:00:00 GMT','ETag':'x'*1100,
                 'Retry-After':'3','Set-Cookie':'secret','Authorization':'secret'}
        (raw,_),_,clock,_=self.collect([Response(b'busy',503,headers),Response(b'{"data":[]}')])
        state=json.loads(raw);self.assertEqual(clock.value,3.)
        self.assertEqual(len(state['attempts']),2)
        for i,(attempt,response) in enumerate(zip(state['attempts'],state['responses'])):
            self.assertEqual(attempt['response_index'],i)
            self.assertEqual(attempt['request_started_at'],response['request_started_at'])
            self.assertEqual(attempt['finished_at'],response['body_completed_at'])
            self.assertLessEqual(attempt['request_started_at'],attempt['finished_at'])
        kept=state['responses'][0]['headers']
        self.assertEqual(set(kept),{'date','etag','retry-after'})
        self.assertTrue(kept['etag']['truncated']);self.assertEqual(len(kept['etag']['value']),1024)
        self.assertNotIn(b'secret',raw)
        day=datetime.now(timezone.utc).date().isoformat();opener=Opener([TimeoutError()]*6);clock=Clock()
        with patch.object(c.request,'build_opener',return_value=opener),patch.object(c.time,'monotonic',clock.monotonic),patch.object(c.time,'sleep',clock.sleep):
            with self.assertRaises(CaptureFailure) as got:c._collect({'query_day':day})
        attempts=json.loads(got.exception.raw_bytes)['attempts']
        self.assertEqual(len(attempts),6)
        self.assertTrue(all(a['status'] is None and a['finished_at'] and a['error']=='TimeoutError' for a in attempts))

    def test_retry_after_seconds_dates_and_budget_stop(self):
        from datetime import timedelta
        from email.utils import format_datetime
        base=datetime.now(timezone.utc).replace(hour=12,minute=0,second=0,microsecond=0)
        for status in (429,503):
            for header in ('11',format_datetime(base+timedelta(seconds=11),usegmt=True)):
                clock=Clock();opener=Opener([Response(b'busy',status,{'Retry-After':header}),Response(b'{"data":[]}')])
                class WallClock(datetime):
                    @classmethod
                    def now(cls,tz):return base+timedelta(seconds=clock.value)
                with patch.object(c,'datetime',WallClock),patch.object(c.request,'build_opener',return_value=opener),patch.object(c.time,'monotonic',clock.monotonic),patch.object(c.time,'sleep',clock.sleep):
                    c._collect({'query_day':base.date().isoformat()})
                self.assertEqual(clock.value,11.);self.assertEqual(len(opener.calls),2)
        for header in ('51','50','999999999999999999999','bad-date','-1'):
            opener=Opener([Response(b'busy',429,{'Retry-After':header}),Response(b'{"data":[]}')]);clock=Clock()
            with patch.object(c.request,'build_opener',return_value=opener),patch.object(c.time,'monotonic',clock.monotonic),patch.object(c.time,'sleep',clock.sleep):
                with self.assertRaisesRegex(CaptureFailure,'Retry-After'):c._collect({'query_day':base.date().isoformat()})
            self.assertEqual(len(opener.calls),1);self.assertEqual(clock.value,0.)

    def test_url_oracle_rejects_credentials_redirects_and_changed_query(self):
        day='2026-11-07';valid=url(day)
        for bad in [valid.replace('https:','http:'),valid.replace(c.HOST,'evil.test'),valid.replace(c.HOST,'u:p@'+c.HOST),valid.replace(c.HOST,c.HOST+':443'),valid+'&api_key=x',valid+'&assets=btc',valid.replace('PriceUSD','Other'),valid+'#fragment']:
            with self.subTest(bad=bad),self.assertRaises((ValueError,CaptureFailure)):c._url(bad,day)
        with self.assertRaises(CaptureFailure):c._NoRedirect().redirect_request(None,None,None,None,None,None)

    def test_retries_count_and_failure_retains_responses(self):
        day=datetime.now(timezone.utc).date().isoformat();opener=Opener([Response(b'busy',429) for _ in range(6)]);clock=Clock()
        with patch.object(c.request,'build_opener',return_value=opener),patch.object(c.time,'monotonic',clock.monotonic),patch.object(c.time,'sleep',clock.sleep):
            with self.assertRaises(CaptureFailure) as got:c._collect({'query_day':day})
        self.assertEqual(len(opener.calls),6);self.assertEqual(clock.value,10.)
        state=json.loads(got.exception.raw_bytes);self.assertFalse(state['complete']);self.assertEqual(len(state['responses']),6)
        self.assertEqual(got.exception.response_metadata['requests'],6)

    def test_limits_malformed_compression_and_pagination_fail_closed(self):
        day=datetime.now(timezone.utc).date().isoformat()
        variants=[Response(b'x'*(c.MAX_BYTES+1)),Response(b'invalid'),Response(b'{"data":[]}',headers={'Content-Encoding':'gzip'}),
                  Response(c.canonical_bytes({'data':[{}]*10001})),Response(c.canonical_bytes({'data':[],'next_page_token':'a'})),
                  Response(c.canonical_bytes({'data':[],'next_page_url':url(day,'a'),'next_page_token':'b'}))]
        for response in variants:
            with self.subTest(),self.assertRaises(CaptureFailure) as got:self.collect([response])
            self.assertFalse(json.loads(got.exception.raw_bytes)['complete'])

    def test_total_budget_and_deadline_are_not_per_page_loopholes(self):
        day=datetime.now(timezone.utc).date().isoformat()
        pages=[]
        for i in range(3):
            body={'data':[], 'padding':'x'*(1900*1024)}
            if i<2:body.update(next_page_url=url(day,str(i+1)),next_page_token=str(i+1))
            pages.append(Response(c.canonical_bytes(body)))
        with self.assertRaisesRegex(CaptureFailure,'total byte limit') as got:self.collect(pages)
        self.assertLess(len(got.exception.raw_bytes),8*1024*1024)
        opener=Opener([Response(b'{"data":[]}')]);clock=Clock();original=opener.open
        def delayed(*args,**kwargs):
            response=original(*args,**kwargs);clock.value=51.;return response
        with patch.object(c.request,'build_opener',return_value=opener),patch.object(opener,'open',side_effect=delayed),patch.object(c.time,'monotonic',clock.monotonic):
            with self.assertRaisesRegex(CaptureFailure,'deadline'):c._collect({'query_day':day})

    def test_partial_read_preserved_and_hard_timeout_archived(self):
        class Broken(Response):
            def read(self,n):
                if self.tell():raise TimeoutError('partial')
                return super().read(min(3,n))
        day=datetime.now(timezone.utc).date().isoformat();opener=Opener([Broken(b'abcdef')]+[TimeoutError()]*5);clock=Clock()
        with patch.object(c.request,'build_opener',return_value=opener),patch.object(c.time,'monotonic',clock.monotonic),patch.object(c.time,'sleep',clock.sleep):
            with self.assertRaises(CaptureFailure) as got:c._collect({'query_day':day})
        partial=got.exception.raw_bytes
        self.assertEqual(base64.b64decode(json.loads(partial)['responses'][0]['body_base64']),b'abc')
        def hung(args,**kw):
            self.assertEqual(kw['timeout'],55);self.assertNotIn('HTTPS_PROXY',kw['env']);self.assertNotIn('shell',kw)
            Path(args[-1]).write_bytes(partial)
            raise subprocess.TimeoutExpired(args,55)
        with tempfile.TemporaryDirectory(dir='/private/tmp') as t,patch.object(c.subprocess,'run',side_effect=hung):
            dest=Path(t)/'capture'
            with self.assertRaises(CaptureFailure):capture_response(dest,{'query_day':day},c.fetch)
            self.assertEqual((dest/'partial.bin').read_bytes(),partial)
            self.assertEqual(json.loads((dest/'failure.json').read_bytes())['status'],'failed_capture')
            with self.assertRaises(ValueError):verify_capture(dest)


class ProducerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.day='2024-02-28';cls.rows=synthetic(cls.day);cls.raw=envelope(cls.day,cls.rows)
        with patch.object(c.request,'build_opener',side_effect=AssertionError('pure producer network')),patch.object(c.subprocess,'run',side_effect=AssertionError('pure producer process')):
            cls.result=c.produce((cls.raw,),c.CONFIG,cls.day)

    def test_actual_model_synthetic_end_to_end_shape_and_repeatability(self):
        result=self.result;self.assertEqual(len(result['forecasts']),6)
        self.assertLess(len(c.canonical_bytes(result)),1024*1024)
        self.assertEqual(result['selected'][0]['closed_at'],self.day+'T00:00:00Z')
        self.assertEqual(result['selected'][0]['prefix']['first_close_at'],'2017-01-02T00:00:00Z')
        for f in result['forecasts']:
            n=8192 if f['interpretation']=='iid_predictive_law_draws' else 24
            self.assertEqual(len(f['atoms']),n);self.assertEqual(len(f['weights']),n)
            self.assertTrue(np.isfinite(f['atoms']).all());self.assertAlmostEqual(sum(f['weights']),1.)
        self.assertTrue(all(np.isfinite(v) for v in result['features'].values()))
        self.assertEqual(result,c.produce((self.raw,),c.CONFIG,self.day))

    def test_independent_context_labels_weights_and_crps(self):
        closes=pd.Series([float(r['PriceUSD']) for r in self.rows],index=pd.date_range('2017-01-02',self.day))
        logs=np.log(closes);query=pd.Timestamp(self.day)
        self.assertAlmostEqual(self.result['features']['context_trend_12m'],logs[query]-logs[query-pd.DateOffset(months=12)])
        self.assertAlmostEqual(self.result['features']['context_volatility_90d'],np.std(np.diff(logs.iloc[-91:]),ddof=1))
        for h in (12,24):
            candidates=[]
            for decision in pd.date_range('2018-01-31',query,freq='ME'):
                entry=decision+pd.Timedelta(days=1);end=entry+pd.DateOffset(months=h)
                if end+pd.Timedelta(days=1)<query:
                    candidates.append((decision,float(logs[end]-logs[entry])))
            candidates=candidates[-24:]
            empirical=next(f for f in self.result['forecasts'] if f['horizon_months']==h and f['model']=='unconditional')
            np.testing.assert_allclose(empirical['atoms'],[v for _,v in candidates],atol=1e-14)
            train=np.array([[logs[d]-logs[d-pd.DateOffset(months=12)],np.std(np.diff(logs.loc[:d].iloc[-91:]),ddof=1)] for d,_ in candidates])
            q=np.array([self.result['features']['context_trend_12m'],self.result['features']['context_volatility_90d']]);cut=np.median(train,axis=0)
            cell=np.all((train>cut)==(q>cut),axis=1);weights=np.ones(24)/24
            if cell.any():weights=.5*weights+.5*cell/cell.sum()
            context=next(f for f in self.result['forecasts'] if f['horizon_months']==h and f['model']=='context')
            np.testing.assert_array_equal(context['weights'],weights)
            x=np.array(context['atoms']);expected=np.sum(weights*abs(x))-.5*np.sum(weights[:,None]*weights[None,:]*abs(x[:,None]-x[None,:]))
            self.assertAlmostEqual(weighted_crps(x,weights,0.),expected,places=13)

    def test_future_poison_prefix_and_physical_value_oracle(self):
        poisoned=self.rows+[{'time':self.day+'T00:00:00Z','asset':'wrong','PriceUSD':{'poison':True}}, {'time':'2030-01-01T00:00:00Z','PriceUSD':'nan'}]
        self.assertEqual(c.closed_prefix(self.raw,self.day),c.closed_prefix(envelope(self.day,poisoned),self.day))
        for value in [0,-1,float('inf'),'NaN',True,None,{},'']:
            rows=[*self.rows[:-1],{**self.rows[-1],'PriceUSD':value}]
            with self.subTest(value=value),self.assertRaises((ValueError,TypeError)):c.closed_prefix(envelope(self.day,rows),self.day)
        for rows in [self.rows[:-1],self.rows[:20]+self.rows[21:],self.rows+[self.rows[-1]]]:
            with self.assertRaises(ValueError):c.closed_prefix(envelope(self.day,rows),self.day)
        before='2023-01-31';short=[r for r in self.rows if r['time']<before+'T00:00:00Z']
        self.assertEqual(c.closed_prefix(self.raw,before),c.closed_prefix(envelope(before,short),before))

    def test_strict_maturity_day_boundary_and_calendar_holding(self):
        # Availability Feb2 is excluded at queryFeb2 and included at queryFeb3.
        for day in ['2024-02-02','2024-02-03','2023-02-28']:
            rows=synthetic(day);raw=envelope(day,rows)
            with patch.object(c.generative,'fit',return_value=type('P',(),{'diagnostics':{
                **{k:1. for k in ('grid_count','outer_edge_strip_mass','posterior_mean_mu','posterior_variance_mu','posterior_mean_scale_squared','posterior_mean_next_variance')},
                'convergence_trace':[{k:0. for k in c.generative.PROTOCOL['tolerances']}]}})()),patch.object(c.generative,'simulate',return_value=np.zeros((8192,2,3))) as sim:
                result=c.produce((raw,),c.CONFIG,day)
            entry=pd.Timestamp(day)+pd.Timedelta(days=1)
            self.assertEqual(sim.call_args.args[1],[int((entry+pd.DateOffset(months=h)-entry).days) for h in (12,24)])
            self.assertEqual(sim.call_args.kwargs['seed'],c.seed(day))
            if day=='2023-02-28':self.assertEqual(sim.call_args.args[1],[366,731])
            closes=pd.Series([float(r['PriceUSD']) for r in rows],index=pd.date_range('2017-01-02',day));logs=np.log(closes)
            last_entry=pd.Timestamp('2022-01-01' if day=='2024-02-02' else '2022-02-01') if day.startswith('2024') else None
            if last_entry is not None:
                f=next(f for f in result['forecasts'] if f['model']=='unconditional' and f['horizon_months']==24)
                self.assertAlmostEqual(f['atoms'][-1],logs[last_entry+pd.DateOffset(months=24)]-logs[last_entry])

    def test_realistic_2017_to_2026_payload_caps(self):
        day='2026-11-07';rows=synthetic(day)
        result=c.produce((envelope(day,rows),),c.CONFIG,day)
        prefix=result['selected'][0]['prefix']
        self.assertEqual(len(prefix['prices']),3597)
        self.assertLess(len(c.canonical_bytes(prefix)),128*1024)
        # Leave ample headroom for the v3 event's provenance/calendar fields.
        self.assertLess(len(c.canonical_bytes(result)),800*1024)
        config=json.loads(Path(c.__file__).with_name('coinmetrics_shadow_config.json').read_bytes())
        self.assertEqual(config,c.CONFIG)

    def test_actual_producer_through_v3_capture_issue_verify(self):
        from research import shadow_capture as cap, shadow_archive_v3 as archive
        class FixedDate(datetime):
            @classmethod
            def now(cls,tz):return datetime(2026,11,7,12,tzinfo=timezone.utc)
        day='2026-11-07';raw=envelope(day,synthetic(day))
        with tempfile.TemporaryDirectory(dir='/private/tmp') as temp,patch.object(cap,'datetime',FixedDate):
            root=Path(temp);captured=root/'capture';store=root/'archive'
            cap.capture_response(captured,{'query_day':day},lambda request:(raw,{'status':'complete','synthetic':True}))
            reg=archive.register({'kind':'operational_witness','decision_days':[day],
                'entry_observation_buffer_seconds':7200},c.produce,c.CODE_PATHS,c.CONFIG)
            archive.initialize(store,reg)
            event=archive.issue(store,[captured],c.produce)
            self.assertEqual(archive.verify(store,event['head_sha256'])['observation_count'],1)
            owned=next((store/'captures').iterdir())
            self.assertEqual(cap.verify_capture(owned)[0],raw)
            event_raw=next((store/'events').iterdir()).read_bytes()
            self.assertLess(len(event_raw),1024*1024)
            issued=json.loads(event_raw)['request']
            self.assertEqual(len(issued['forecasts']),6)
            self.assertEqual(len(issued['selected'][0]['prefix']['prices']),3597)
            self.assertTrue(all(f['entry_at'].startswith('2026-11-08T00:00:00') for f in issued['forecasts']))

    def test_fit_failure_no_fallback_and_fixed_config(self):
        with patch.object(c.generative,'fit',side_effect=c.generative.FitError('synthetic failure')):
            with self.assertRaisesRegex(c.generative.FitError,'synthetic failure'):c.produce((self.raw,),c.CONFIG,self.day)
        with self.assertRaises(ValueError):c.produce((self.raw,),{**c.CONFIG,'seed_base':9},self.day)

if __name__=='__main__':unittest.main()
