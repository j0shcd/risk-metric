"""Coin Metrics local noncommercial PAPER witness; no trading or publication rights.

API: fetch({'query_day': 'YYYY-MM-DD'}) is the explicit network callback for
shadow_capture.capture_response. produce((owned_raw_bytes,), CONFIG, query_day)
is pure and emits six forecasts; register it with CODE_PATHS and the companion
coinmetrics_shadow_config.json. No acquisition or CLI runs on import. The sole
module CLI is an internal fixed worker called by fetch, not a user entrypoint.

Canonical protocol, provider evidence, rights scope, status and run authorization:
docs/metric_evaluation_plan.md. No actual acquisition is authorized by this module.
"""
from __future__ import annotations
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import tempfile
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib import error, parse, request
import numpy as np
import pandas as pd
from .market_dataset import COMPONENTS, build_dataset, canonical_bytes
from .distribution_readout import mixture_forecasts
from . import generative_price_baseline as generative
from .shadow_capture import CaptureFailure

ROOT = Path(__file__).resolve().parents[1]
HOST = 'community-api.coinmetrics.io'
PATH = '/v4/timeseries/asset-metrics'
START = '2017-01-01'
MAX_REQUESTS, MAX_BYTES, MAX_ROWS = 6, 2*1024*1024, 10000
MAX_TOTAL_BYTES = 5*1024*1024  # base64 envelope remains below v3 capture limit8MiB
CONFIG = {
    'protocol':'coinmetrics-paper-baselines-v1', 'asset':'btc', 'metric':'PriceUSD',
    'frequency':'1d', 'start_bar_day':START, 'seed_base':20261107,
    'entry_observation_buffer_seconds':7200,
    'horizons':[12,24], 'mature_labels':24, 'generative_paths':8192,
    'freshness':'latest selected close must equal query-day00:00UTC',
    'rights':'local noncommercial PAPER infrastructure research only; trading/commercial/publication rights unestablished',
}

# Registration callers must bind these helpers as well as the v3 boundary.
CODE_PATHS = tuple(Path(__file__).with_name(name) for name in (
    'coinmetrics_shadow.py','market_dataset.py','distribution_readout.py',
    'generative_price_baseline.py','shadow_capture.py','scorecard_artifacts.py'))

class CaptureError(CaptureFailure): pass
class QualityError(ValueError): pass


def _day(value):
    if not isinstance(value,str):raise ValueError('ISO date required')
    d=pd.Timestamp(value)
    if d.tzinfo is not None or d!=d.normalize() or d.date().isoformat()!=value:
        raise ValueError('ISO calendar date required')
    return d


def _parameters(query_day):
    _day(query_day)
    return {'assets':'btc','metrics':'PriceUSD','frequency':'1d',
            'start_time':START+'T00:00:00Z','end_time':query_day+'T00:00:00Z',
            'end_inclusive':'false','format':'json','page_size':'10000','paging_from':'start'}


def _url(url, query_day):
    u=parse.urlsplit(url)
    if (u.scheme!='https' or u.netloc!=HOST or u.path!=PATH or u.fragment or len(url)>8192):
        raise CaptureError('only fixed public HTTPS endpoint allowed')
    pairs=parse.parse_qsl(u.query,keep_blank_values=True,strict_parsing=True)
    params=dict(pairs);expected=_parameters(query_day)
    if len(params)!=len(pairs) or set(params)-set(expected)-{'next_page_token'}:
        raise CaptureError('unexpected or duplicate query parameters')
    if any(params.get(k)!=v for k,v in expected.items()):raise CaptureError('pagination changed fixed query')
    if 'next_page_token' in params and not 0<len(params['next_page_token'])<=4096:
        raise CaptureError('invalid page token')
    return url


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise CaptureError('redirect forbidden')


def _stamp():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')


def _headers(headers):
    """Bounded allowlist only; never retain cookies or authentication headers."""
    names=('Date','Last-Modified','ETag','Cache-Control','Content-Type',
           'Content-Length','Content-Encoding','Retry-After','X-Request-ID')
    selected={}
    for name in names:
        value=headers.get(name)
        if value is None:continue
        value=str(value);raw=value.encode('utf8')
        selected[name.lower()]={'value':raw[:1024].decode('utf8',errors='replace'),
            'truncated':len(raw)>1024,'sha256':hashlib.sha256(raw).hexdigest()}
    return selected


def _retry_delay(value):
    """RFC Retry-After seconds/date; malformed or overlong directives stop retries."""
    if value is None:return 0.
    value=str(value).strip()
    if not value or len(value)>1024:raise CaptureError('invalid Retry-After')
    if value.isascii() and value.isdigit():
        if len(value)>6:raise CaptureError('Retry-After exceeds worker budget')
        return float(int(value))
    try:
        until=parsedate_to_datetime(value)
        if until.tzinfo is None:raise ValueError('timezone absent')
        return max(0.,(until-datetime.now(timezone.utc)).total_seconds())
    except (TypeError,ValueError,OverflowError) as exc:raise CaptureError('invalid Retry-After') from exc


def _collect(metadata, checkpoint=None):
    """Internal worker; every obtained response is checkpointed before parsing."""
    if set(metadata)!={'query_day'}:raise CaptureError('only query_day request metadata allowed')
    query_day=metadata['query_day'];_day(query_day)
    if query_day!=datetime.now(timezone.utc).date().isoformat():raise CaptureError('capture requires actual current UTC day')
    url='https://'+HOST+PATH+'?'+parse.urlencode(_parameters(query_day))
    opener=request.build_opener(request.ProxyHandler({}),_NoRedirect())
    state={'schema':'coinmetrics-exact-pages-v1','query_day':query_day,'complete':False,'responses':[],'pages':[],'errors':[],'attempts':[]}
    def save():
        if checkpoint is not None:checkpoint(canonical_bytes(state))
    save()
    started=time.monotonic();last=None;not_before=started;attempts=rows=0;seen=set()
    try:
        while url is not None:
            _url(url,query_day)
            if url in seen:raise CaptureError('repeated pagination URL')
            if attempts>=MAX_REQUESTS:raise CaptureError('six request budget exhausted')
            current=time.monotonic()
            wait=max(0.,not_before-current,0. if last is None else last+2-current)
            if wait>=50-(current-started):raise CaptureError('Retry-After/rate wait exceeds worker budget')
            if wait:time.sleep(wait)
            remaining=50-(time.monotonic()-started)
            if remaining<=0:raise CaptureError('collector deadline exceeded')
            last=time.monotonic();attempts+=1
            attempt={'number':attempts,'url':url,'request_started_at':_stamp(),
                     'finished_at':None,'status':None,'response_index':None,'error':None}
            state['attempts'].append(attempt);save()
            try:
                req=request.Request(url,headers={'Accept':'application/json','Accept-Encoding':'identity',
                                                'User-Agent':'local-noncommercial-paper-witness/1'})
                try:response=opener.open(req,timeout=min(10.,remaining))
                except error.HTTPError as exc:response=exc
                with response:
                    entry={'url':url,'status':response.status,'headers':_headers(response.headers),
                           'request_started_at':attempt['request_started_at'],'body_completed_at':None,
                           'body_base64':'','body_complete':False}
                    attempt.update(status=response.status,response_index=len(state['responses']))
                    state['responses'].append(entry);save()
                    previous_bytes=sum(len(base64.b64decode(r['body_base64'])) for r in state['responses'][:-1])
                    bound=min(MAX_BYTES,MAX_TOTAL_BYTES-previous_bytes)
                    raw=b''
                    while True:
                        chunk=response.read(min(65536,bound+1-len(raw)))
                        if not chunk:break
                        raw+=chunk
                        entry['body_base64']=base64.b64encode(raw).decode('ascii');save()
                        if len(raw)>bound:raise CaptureError('response or total byte limit')
                    entry['body_complete']=True;entry['body_completed_at']=_stamp()
                    attempt['finished_at']=entry['body_completed_at'];save()
                    if response.headers.get('Content-Encoding','identity')!='identity':raise CaptureError('compressed response forbidden')
                    if response.status!=200:
                        if response.status in (429,500,502,503,504):
                            delay=_retry_delay(response.headers.get('Retry-After')) if response.status in (429,503) else 0.
                            not_before=time.monotonic()+delay
                            if not_before-started>=50:raise CaptureError('Retry-After exceeds worker budget')
                            continue
                        raise CaptureError('nonretryable HTTP status')
                    if time.monotonic()-started>50:raise CaptureError('collector deadline exceeded')
                    body=json.loads(raw,parse_float=str,parse_int=str,parse_constant=str)
            except (error.URLError,TimeoutError) as exc:
                attempt.update(finished_at=_stamp(),error=type(exc).__name__)
                state['errors'].append({'attempt':attempts,'error':type(exc).__name__});save();continue
            if not isinstance(body,dict) or not isinstance(body.get('data'),list):raise CaptureError('invalid response shape')
            rows+=len(body['data'])
            if rows>MAX_ROWS:raise CaptureError('row budget exceeded')
            state['pages'].append(len(state['responses'])-1);seen.add(url);save()
            next_url=body.get('next_page_url');token=body.get('next_page_token')
            if next_url is None and token is not None:raise CaptureError('token without next page URL')
            if next_url is not None:
                _url(next_url,query_day)
                if not token or dict(parse.parse_qsl(parse.urlsplit(next_url).query)).get('next_page_token')!=token:
                    raise CaptureError('page token/URL mismatch')
            url=next_url
        state['complete']=True;save()
    except Exception as exc:
        if state['attempts'] and state['attempts'][-1]['finished_at'] is None:
            state['attempts'][-1].update(finished_at=_stamp(),error=type(exc).__name__)
        state['errors'].append({'attempt':attempts,'error':type(exc).__name__+': '+str(exc)[:400]});save()
        failure=CaptureError(str(exc));failure.raw_bytes=canonical_bytes(state)
        failure.response_metadata={'status':'failed','requests':attempts,'pages':len(state['pages'])}
        raise failure from exc
    return canonical_bytes(state),{'status':'complete','provider':'Coin Metrics Community','requests':attempts,
        'pages':len(state['pages']),'rows':rows,'transport':'stdlib verified HTTPS; no auth/proxy/cookies/redirects','rights':CONFIG['rights']}


def fetch(request_metadata):
    """v3 fetch callback. Owned subprocess timeout55s kills/reaps DNS/read stalls.

    All completed/partial response bytes checkpointed by worker are attached to
    CaptureError for the capture boundary to retain. Never forecast incomplete.
    """
    if not isinstance(request_metadata,dict) or set(request_metadata)!={'query_day'}:raise CaptureError('invalid request metadata')
    _day(request_metadata['query_day'])
    env={k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL','SYSTEMROOT')}
    with tempfile.TemporaryDirectory(prefix='coinmetrics-owned-',dir='/private/tmp') as temporary:
        checkpoint=Path(temporary)/'partial.json'
        try:
            result=subprocess.run([sys.executable,'-m','research.coinmetrics_shadow','--collector-worker',str(checkpoint)],
                input=canonical_bytes(request_metadata),stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                timeout=55,check=False,cwd=ROOT,env=env)
            if result.returncode:raise CaptureError('collector failed: '+result.stderr.decode('utf8',errors='replace')[:500])
            metadata=json.loads(result.stdout)
            return checkpoint.read_bytes(),metadata
        except (subprocess.TimeoutExpired,CaptureError,OSError,ValueError) as exc:
            failure=CaptureError('hard collector timeout; worker killed' if isinstance(exc,subprocess.TimeoutExpired) else str(exc))
            failure.raw_bytes=checkpoint.read_bytes() if checkpoint.exists() else b''
            failure.response_metadata={'status':'failed','error':str(failure),'partial_response_capture':True}
            raise failure from exc


def closed_prefix(raw,query_day):
    """Select by timestamps BEFORE reading price values; no future bar influence."""
    query=_day(query_day)
    if len(raw)>8*1024*1024:raise QualityError('capture envelope byte limit')
    envelope=json.loads(raw)
    if envelope.get('schema')!='coinmetrics-exact-pages-v1':raise QualityError('unsupported capture schema')
    capture_day=envelope['query_day'];_day(capture_day)
    if envelope.get('complete') is not True:raise QualityError('incomplete capture')
    responses=envelope['responses'];indices=envelope['pages']
    if not isinstance(responses,list) or len(responses)>MAX_REQUESTS or not isinstance(indices,list) or len(set(indices))!=len(indices):raise QualityError('invalid response inventory')
    if any(type(i) is not int or i<0 or i>=len(responses) for i in indices):raise QualityError('invalid page index')
    pages=[responses[i] for i in indices]
    if not isinstance(pages,list) or not 1<=len(pages)<=MAX_REQUESTS:raise QualityError('invalid page count')
    points={};rows=0;previous_next=None
    for i,page in enumerate(pages):
        if page.get('status')!=200 or page.get('body_complete') is not True:raise QualityError('non-success or partial page')
        url=_url(page['url'],capture_day)
        if i and url!=previous_next:raise QualityError('captured pagination chain mismatch')
        if not i and 'next_page_token' in dict(parse.parse_qsl(parse.urlsplit(url).query)):raise QualityError('capture begins mid-pagination')
        payload=base64.b64decode(page['body_base64'],validate=True)
        if len(payload)>MAX_BYTES:raise QualityError('page byte limit')
        body=json.loads(payload)
        if not isinstance(body,dict) or not isinstance(body.get('data'),list):raise QualityError('invalid page shape')
        previous_next=body.get('next_page_url');rows+=len(body['data'])
        if rows>MAX_ROWS:raise QualityError('row budget exceeded')
        for row in body['data']:
            if not isinstance(row,dict):raise QualityError('invalid row')
            stamp=row.get('time')
            if not isinstance(stamp,str) or not stamp.endswith('Z'):raise QualityError('UTC bar timestamp required')
            bar=pd.Timestamp(stamp)
            if pd.isna(bar) or bar!=bar.normalize():raise QualityError('daily bar must start at UTC midnight')
            close=(bar+pd.Timedelta(days=1)).tz_localize(None)
            if close>query:continue
            if bar.tz_localize(None)<pd.Timestamp(START):continue
            if set(row)!={'asset','time','PriceUSD'} or row['asset']!='btc':raise QualityError('unexpected asset or metric')
            if isinstance(row['PriceUSD'],bool):raise QualityError('price must be positive numeric')
            try:value=float(row['PriceUSD'])
            except (ValueError,TypeError) as exc:raise QualityError('invalid price') from exc
            if not math.isfinite(value) or value<=0:raise QualityError('nonpositive/nonfinite close')
            if close in points:raise QualityError('duplicate close')
            points[close]=value
    if previous_next is not None:raise QualityError('incomplete captured pagination')
    expected=pd.date_range(pd.Timestamp(START)+pd.Timedelta(days=1),query,freq='D')
    if not points or max(points)!=query:raise QualityError('stale_source_quality_gate: current UTC close absent')
    if sorted(points)!=list(expected):raise QualityError('daily close gap; no interpolation')
    return [{'Date':day.date().isoformat()+'T00:00:00Z','Price':points[day]} for day in expected]


def seed(query_day):
    return int.from_bytes(hashlib.sha256(f"{CONFIG['seed_base']}:{query_day}".encode()).digest()[:8],'big')


def produce(raw_bytes_tuple,config,query_day):
    """Pure v3 producer: closed-date source convention, no network or fallbacks."""
    if config!=CONFIG:raise ValueError('fixed producer configuration changed')
    if not isinstance(raw_bytes_tuple,tuple) or len(raw_bytes_tuple)!=1:raise ValueError('exactly one capture envelope required')
    prefix=closed_prefix(raw_bytes_tuple[0],query_day);query=_day(query_day)
    dates=pd.DatetimeIndex([r['Date'] for r in prefix]).tz_localize(None)
    logs=pd.Series(np.log([r['Price'] for r in prefix]),index=dates)
    if len(logs)<731:raise QualityError('730 daily returns required')
    lookback=query-pd.DateOffset(years=1)
    if lookback not in logs.index:raise QualityError('query context unavailable')
    context=np.array([logs.loc[query]-logs.loc[lookback],logs.diff().iloc[-90:].std(ddof=1)])
    snapshot={'schema':'price-only-close-instant-v1','daily':[{'date':r['Date'][:10],'price':r['Price']} for r in prefix],
              'monthly':[{'date':d.date().isoformat(),**{c:None for c in COMPONENTS}} for d in pd.date_range(dates.min(),query,freq='ME')]}
    rows=build_dataset(snapshot,[12,24])['rows']
    features={'context_trend_12m':float(context[0]),'context_volatility_90d':float(context[1]),'source_close_n':float(len(prefix))}
    forecasts=[]
    for h in CONFIG['horizons']:
        mature=[r for r in rows if r['date']<query_day and r['context'] is not None and r['outcomes'][str(h)]['status']=='complete' and r['outcomes'][str(h)]['available']<query_day][-24:]
        if len(mature)!=24:raise QualityError(f'insufficient strictly mature monthly labels:{h}')
        train=np.array([r['context'] for r in mature]);atoms=[r['outcomes'][str(h)]['values'][0] for r in mature]
        mix=mixture_forecasts(train,train,context)
        features[f'train_{h}_n']=24.;features[f'context_{h}_cell_n']=float(mix['context_cell_n']);features[f'context_{h}_fallback']=float(mix['context_fallback'])
        for model,weights in [('unconditional',np.full(24,1/24)),('context',mix['reference'])]:
            forecasts.append({'model':model,'interpretation':'issued_cdf','target':'terminal_log_return','horizon_months':h,'atoms':atoms,'weights':weights.tolist()})
    posterior=generative.fit(np.diff(logs.iloc[-731:].to_numpy()))  # FitError deliberately propagates; never fallback.
    entry=query+pd.Timedelta(days=1);holding=[int(((entry+pd.DateOffset(months=h))-entry).days) for h in CONFIG['horizons']]
    draws=generative.simulate(posterior,holding,seed=seed(query_day))
    if draws.shape!=(8192,2,3) or not np.isfinite(draws).all():raise generative.FitError('invalid frozen simulation output')
    for key in ('grid_count','outer_edge_strip_mass','posterior_mean_mu','posterior_variance_mu','posterior_mean_scale_squared','posterior_mean_next_variance'):
        features['generative_'+key]=float(posterior.diagnostics[key])
    for key in generative.PROTOCOL['tolerances']:
        features['generative_'+key]=float(posterior.diagnostics['convergence_trace'][-1][key])
    for i,h in enumerate(CONFIG['horizons']):
        forecasts.append({'model':generative.PROTOCOL['id'],'interpretation':'iid_predictive_law_draws','target':'terminal_log_return','horizon_months':h,'atoms':draws[:,i,0].tolist(),'weights':[1/8192]*8192})
    selected={'first_close_at':prefix[0]['Date'],'step_seconds':86400,'prices':[r['Price'] for r in prefix]}
    if len(canonical_bytes(selected))>128*1024:raise QualityError('selected prefix exceeds archive cap')
    return {'selected':[{'capture_index':0,'closed_at':query_day+'T00:00:00Z','prefix':selected}], 'features':features,'forecasts':forecasts}


if __name__=='__main__':
    if len(sys.argv)!=3 or sys.argv[1]!='--collector-worker':raise SystemExit('Only internal collector worker is supported; use reviewed v3 capture boundary.')
    destination=Path(sys.argv[2])
    def checkpoint(raw):
        staged=destination.with_suffix('.staged')
        staged.write_bytes(raw);staged.replace(destination)
    try:
        raw,metadata=_collect(json.loads(sys.stdin.buffer.read(4097)),checkpoint)
        sys.stdout.buffer.write(canonical_bytes(metadata))
    except Exception as exc:
        sys.stderr.write(type(exc).__name__+': '+str(exc)[:400]);raise SystemExit(1)
