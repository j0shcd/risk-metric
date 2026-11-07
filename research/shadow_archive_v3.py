"""Offline v3 capture-to-producer archive; v2 remains immutable and unsupported.

Local ownership and chronology are not publication-vintage authentication,
calibration, freshness or fitness. An independently retained head is necessary
against adversarial tail deletion/full rewrite. The public head binds every
scientific file, including failed attempts and orphan captures; event linkage is
a separate chain head. Lock contents alone are explicitly non-scientific. Producer purity/source selection
is reviewed, not a Python sandbox; no arbitrary module loading is provided.
Raw captures have a separate128MiB budget, events64MiB, per-event1MiB/2048events.
Exclusive attempts remain visible after failure/interruption and consume that
cohort day. No scheduler, trading, network transport or production promotion.
"""
from __future__ import annotations
from contextlib import contextmanager
from datetime import timedelta
import fcntl
import inspect
import json
import math
from pathlib import Path
import platform
import re
import sys
import types
import numpy as np
import pandas as pd
from . import shadow_capture as cap
from .market_dataset import canonical_bytes
from .shadow_archive import label_calendar

SCHEMA='research-shadow-archive-v3'
MAX_EVENT_BYTES=1024*1024
MAX_ARCHIVE_BYTES=64*1024*1024
MAX_EVENTS=2048
MAX_PREFIX_BYTES=128*1024
MAX_PARENTS=8
MAX_FORECASTS=16


def now():return cap.now()
def digest(value):return cap.sha(canonical_bytes(value))
def runtime():return {'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__}
def keys(value,names):
    if not isinstance(value,dict) or set(value)!=set(names):raise ValueError('unexpected/missing fields')
def finite(value):
    if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('finite numeric value required')
def code_hash(code):
    """Stable semantic bytecode hash; marshal's intern-reference encoding can drift."""
    def constant(value):
        if isinstance(value,types.CodeType):return {'code':code_hash(value)}
        if isinstance(value,bytes):return {'bytes':value.hex()}
        if isinstance(value,tuple):return {'tuple':[constant(v) for v in value]}
        if isinstance(value,frozenset):return {'frozenset':sorted([constant(v) for v in value],key=repr)}
        if value is Ellipsis:return {'ellipsis':True}
        if isinstance(value,complex):return {'complex':[value.real,value.imag]}
        return value
    return digest({'bytecode':code.co_code.hex(),'constants':[constant(v) for v in code.co_consts],
                   'names':code.co_names,'variables':code.co_varnames,'free':code.co_freevars,'cells':code.co_cellvars,
                   'argcount':code.co_argcount,'posonly':code.co_posonlyargcount,'kwonly':code.co_kwonlyargcount,
                   'flags':code.co_flags,'exceptiontable':code.co_exceptiontable.hex()})


def default_value(value):
    """Bounded data defaults only; no repr/address-dependent object identities."""
    if value is None or type(value) in (str,int,bool):return value
    if type(value) is float:
        finite(value);return value
    if isinstance(value,bytes):return {'bytes':value.hex()}
    if isinstance(value,(tuple,list)):return {type(value).__name__:[default_value(v) for v in value]}
    if isinstance(value,(set,frozenset)):return {type(value).__name__:sorted([default_value(v) for v in value],key=canonical_bytes)}
    if isinstance(value,dict):
        if not all(isinstance(k,str) for k in value):raise ValueError('string default keys required')
        return {k:default_value(v) for k,v in value.items()}
    raise ValueError('unsupported non-data callable default')


def function_identity(function):
    return {'code':code_hash(function.__code__),'defaults':default_value(function.__defaults__),
            'kwdefaults':default_value(function.__kwdefaults__)}


def source_identity(producer,paths):
    if not inspect.isfunction(producer) or producer.__closure__ or '<locals>' in producer.__qualname__:raise ValueError('top-level pure Python producer required')
    paths=sorted({str(cap.safe(p).resolve()) for p in paths})
    origin=str(Path(inspect.getsourcefile(producer)).resolve())
    if origin not in paths:raise ValueError('producer source absent from closure')
    # Bind actual loaded Python function bodies as well as source bytes. Imported
    # third-party libraries are version-bound; native execution is not sandboxed.
    loaded={}
    for module in list(sys.modules.values()):
        location=getattr(module,'__file__',None)
        if not location or str(Path(location).resolve()) not in paths:continue
        for name,value in vars(module).copy().items():
            if inspect.isfunction(value) and value.__module__==module.__name__:
                loaded[module.__name__+'.'+name]=function_identity(value)
    return {'entrypoint':producer.__module__+':'+producer.__qualname__,'code':{p:cap.sha(cap.read(p,cap.MAX_RESPONSE_BYTES)) for p in paths},
            'loaded_functions':loaded,'callable_code':function_identity(producer),'runtime':runtime()}


def register(cohort,producer,code_paths,config):
    """Pin explicit permissible UTC dates; operational and monthly cohorts differ."""
    keys(cohort,('kind','decision_days','entry_observation_buffer_seconds'))
    days=cohort['decision_days']
    if cohort['kind'] not in ('operational_witness','formal_monthly') or not isinstance(days,list) or not days or len(days)>MAX_EVENTS or days!=sorted(set(days)):raise ValueError('cohort definition')
    for day in days:
        date=pd.Timestamp(day)
        if date.tz is not None or date.date().isoformat()!=day:raise ValueError('ISO day required')
        if cohort['kind']=='formal_monthly' and date!=date+pd.offsets.MonthEnd(0):raise ValueError('formal cohort must use month ends')
    if not isinstance(config,dict):raise ValueError('config dict required')
    buffer=cohort['entry_observation_buffer_seconds']
    if type(buffer) is not int or not 0<=buffer<86400 or config.get('entry_observation_buffer_seconds')!=buffer:raise ValueError('cohort/config entry buffer mismatch')
    identity=source_identity(producer,[*code_paths,Path(__file__),Path(cap.__file__),Path(__file__).with_name('market_dataset.py'),Path(__file__).with_name('scorecard_artifacts.py'),Path(__file__).with_name('shadow_archive.py')])
    reg={'schema':SCHEMA,'cohort':cohort,'config':config,'producer':identity,
         'calendar':{'anchors':'next UTC day00 entry; calendar-month end; next-day label availability','entry_observation_buffer_seconds':buffer},
         'limits':{'event_bytes':MAX_EVENT_BYTES,'archive_bytes':MAX_ARCHIVE_BYTES,'events':MAX_EVENTS,'capture_bytes':cap.MAX_CAPTURE_BYTES}}
    reg=json.loads(canonical_bytes(reg));reg['registration_id']=digest(reg)
    return reg


def _registration(reg):
    keys(reg,('schema','cohort','config','producer','calendar','limits','registration_id'))
    if reg['schema']!=SCHEMA or reg['registration_id']!=digest({k:v for k,v in reg.items() if k!='registration_id'}):raise ValueError('v3 registration identity required; no v2 reclassification')
    cohort=reg['cohort'];keys(cohort,('kind','decision_days','entry_observation_buffer_seconds'))
    days=cohort['decision_days']
    if cohort['kind'] not in ('operational_witness','formal_monthly') or not isinstance(days,list) or not days or len(days)>MAX_EVENTS or days!=sorted(set(days)):raise ValueError('registered cohort definition')
    for day in days:
        date=pd.Timestamp(day)
        if date.tz is not None or date.date().isoformat()!=day:raise ValueError('registered ISO day')
        if cohort['kind']=='formal_monthly' and date!=date+pd.offsets.MonthEnd(0):raise ValueError('registered formal month end')
    buffer=cohort['entry_observation_buffer_seconds']
    if type(buffer) is not int or not 0<=buffer<86400 or not isinstance(reg['config'],dict) or reg['config'].get('entry_observation_buffer_seconds')!=buffer:raise ValueError('registered entry buffer mismatch')
    if reg['calendar']!={'anchors':'next UTC day00 entry; calendar-month end; next-day label availability','entry_observation_buffer_seconds':buffer}:raise ValueError('registered calendar mismatch')
    if reg['limits']!={'event_bytes':MAX_EVENT_BYTES,'archive_bytes':MAX_ARCHIVE_BYTES,'events':MAX_EVENTS,'capture_bytes':cap.MAX_CAPTURE_BYTES}:raise ValueError('registered limits mismatch')


def initialize(root,registration):
    _registration(registration);root=cap.safe(root);cap.new_directory(root)
    cap.frozen_write(root/'registration.json',canonical_bytes(registration))
    cap.frozen_write(root/'archive.lock',b'')
    for name in ('events','captures','attempts','publications'):cap.new_directory(root/name)
    return verify(root)


@contextmanager
def lock(root,exclusive=True):
    root=cap.safe(root)
    with cap.safe(root/'archive.lock').open('rb') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:yield root
        finally:fcntl.flock(stream,fcntl.LOCK_UN)


def _capture(root,identity,cache):
    if not isinstance(identity,str) or not re.fullmatch('[0-9a-f]{64}',identity):raise ValueError('capture hash identity')
    if identity not in cache:cache[identity]=cap.verify_capture(root/'captures'/identity)
    if cache[identity][1]['capture_id']!=identity:raise ValueError('capture directory identity')
    return cache[identity]


def _own_capture(root,directory):
    raw,receipt=cap.verify_capture(directory);target=root/'captures'/receipt['capture_id']
    if target.exists():
        if cap.verify_capture(target)!=(raw,receipt):raise ValueError('existing capture mismatch')
        return receipt
    size=sum(cap.safe(p).stat().st_size for p in (root/'captures').rglob('*') if p.is_file())
    payloads={'raw.bin':raw,'capture.json':canonical_bytes(receipt),'request.json':canonical_bytes(receipt['request'])}
    if size+sum(map(len,payloads.values()))>cap.MAX_CAPTURE_BYTES:raise ValueError('archive capture budget')
    cap.new_directory(target)
    for name,data in payloads.items():cap.frozen_write(target/name,data)
    return receipt


def _forecast_shape(forecasts):
    if not isinstance(forecasts,list) or not 1<=len(forecasts)<=MAX_FORECASTS:raise ValueError('forecast count')
    seen=set()
    for f in forecasts:
        keys(f,('model','interpretation','target','horizon_months','atoms','weights','entry_at','label_end_at','label_available_at'))
        identity=(f['model'],f['target'],f['horizon_months'])
        if (not isinstance(f['model'],str) or not f['model'].strip() or len(f['model'])>128 or identity in seen
                or f['interpretation'] not in ('issued_cdf','iid_predictive_law_draws')
                or f['target'] not in ('terminal_log_return','entry_adverse_log_loss','peak_drawdown_log_loss')
                or type(f['horizon_months']) is not int or f['horizon_months'] not in (12,24)):raise ValueError('forecast identity')
        seen.add(identity);a,w=f['atoms'],f['weights']
        if not isinstance(a,list) or not isinstance(w,list) or not 1<=len(a)<=8192 or len(a)!=len(w):raise ValueError('atom count')
        for v in a+w:finite(v)
        if min(w)<0 or not math.isclose(sum(w),1,rel_tol=0,abs_tol=1e-12):raise ValueError('probability weights')
        if f['target']!='terminal_log_return' and min(a)<0:raise ValueError('negative physical loss')


def _validate_observation(event,reg,root,cache):
    request=event['request'];keys(request,('attempt','attempt_sha256','capture_ids','selected','features','forecasts','issued_at','query_day','producer_output_sha256'))
    issue=cap.time(request['issued_at']);commit=cap.time(event['committed_at'])
    if issue>commit or request['query_day']!=issue.date().isoformat() or request['query_day'] not in reg['cohort']['decision_days']:raise ValueError('issue/cohort chronology')
    if not isinstance(request['features'],dict) or not request['features']:raise ValueError('features required')
    for k,v in request['features'].items():
        if not isinstance(k,str) or not k.strip():raise ValueError('feature name')
        finite(v)
    ids=request['capture_ids'];selected=request['selected']
    if not isinstance(ids,list) or not 1<=len(ids)<=MAX_PARENTS or len(set(ids))!=len(ids) or len(selected)!=len(ids):raise ValueError('capture parent inventory')
    ages=[]
    for i,(identity,item) in enumerate(zip(ids,selected)):
        keys(item,('capture_index','closed_at','prefix','prefix_sha256'))
        raw,capture=_capture(root,identity,cache)
        close=cap.time(item['closed_at']);complete=cap.time(capture['completed_at'])
        if item['capture_index']!=i or not close<=complete<=issue:raise ValueError('closed prefix/capture/issue chronology')
        prefix=canonical_bytes(item['prefix'])
        if len(prefix)>MAX_PREFIX_BYTES or cap.sha(prefix)!=item['prefix_sha256']:raise ValueError('selected prefix identity/size')
        ages.append((issue-close).total_seconds())
    _forecast_shape(request['forecasts'])
    for f in request['forecasts']:
        entry,end,available=label_calendar(issue,f['horizon_months'])
        if tuple(cap.time(f[k]) for k in ('entry_at','label_end_at','label_available_at'))!=(entry,end,available) or commit>=entry-timedelta(seconds=reg['cohort']['entry_observation_buffer_seconds']):raise ValueError('calendar/entry commitment boundary')
    # Hash the exact producer-return shape, before archive-added calendar/hash fields.
    produced={'selected':[{k:v for k,v in s.items() if k!='prefix_sha256'} for s in selected],
              'features':request['features'],'forecasts':[{k:v for k,v in f.items() if k not in ('entry_at','label_end_at','label_available_at')} for f in request['forecasts']]}
    if digest(produced)!=request['producer_output_sha256']:raise ValueError('producer output identity')
    return {'prospective_eligibility':True,'classification':'observed_current_vintage_prospective',
            'source_age_seconds':ages,'quality_flags':['older_source_as_of'] if any(x>=86400 for x in ages) else [],
            'scope':'chronology and supplied producer lineage only; no fitness/authentication claim'}


def _validate_resolution(event,observations,resolved,root,cache):
    r=event['request'];keys(r,('observation_id','model','target','horizon_months','outcome','capture_id','closed_at'))
    key=tuple(r[k] for k in ('observation_id','model','target','horizon_months'))
    if key in resolved or r['observation_id'] not in observations:raise ValueError('unknown/duplicate resolution')
    f=next((f for f in observations[r['observation_id']]['forecasts'] if (f['model'],f['target'],f['horizon_months'])==key[1:]),None)
    if f is None:raise ValueError('unknown model forecast')
    finite(r['outcome'])
    # Models forecast the same realized target, not model-specific source vintages.
    shared=(key[0],key[2],key[3]);evidence=(r['outcome'],r['capture_id'],r['closed_at'])
    if any((k[0],k[2],k[3])==shared and prior!=evidence for k,prior in resolved.items()):
        raise ValueError('conflicting shared outcome or source evidence')
    if r['target']!='terminal_log_return' and r['outcome']<0:raise ValueError('negative physical loss')
    _,capture=_capture(root,r['capture_id'],cache);commit=cap.time(event['committed_at']);closed=cap.time(r['closed_at'])
    if not cap.time(f['label_end_at'])<=closed<=cap.time(capture['completed_at'])<=commit or commit<cap.time(f['label_available_at']):raise ValueError('resolution chronology')
    return key


def _persisted_head(root,event_chain_head):
    """Bind every scientific file, including failed/pending/orphan state.

    Lock bytes are intentionally excluded: they carry no scientific state; the
    lock must still exist for every operation. Paths themselves are hash-bound.
    Event-chain linkage stays separate from this externally retained state head.
    """
    inventory={};scientific_bytes=0;capture_bytes=0
    for path in sorted(root.rglob('*')):
        cap.safe(path)
        if path.is_dir():continue
        name=path.relative_to(root).as_posix()
        if name=='archive.lock':continue
        limit=cap.MAX_RESPONSE_BYTES if name.startswith('captures/') else MAX_EVENT_BYTES
        raw=cap.read(path,limit);inventory[name]=cap.sha(raw)
        if name.startswith('captures/'):capture_bytes+=len(raw)
        else:scientific_bytes+=len(raw)
        if scientific_bytes>MAX_ARCHIVE_BYTES or capture_bytes>cap.MAX_CAPTURE_BYTES:raise ValueError('complete persisted state byte cap')
    return digest({'event_chain_head_sha256':event_chain_head,'scientific_files':inventory}),scientific_bytes,len(inventory)


def _read(root,expected_head=None):
    raw=cap.read(root/'registration.json',MAX_EVENT_BYTES);reg=json.loads(raw);_registration(reg)
    if {p.name for p in root.iterdir()}!={'registration.json','archive.lock','events','captures','attempts','publications'}:raise ValueError('archive inventory')
    files=sorted((root/'events').iterdir());total=len(raw);head=cap.sha(raw);last=None;observations={};resolved={};cache={};days=set()
    if len(files)>MAX_EVENTS:raise ValueError('event count cap')
    for seq,path in enumerate(files,1):
        data=cap.read(path,MAX_EVENT_BYTES);total+=len(data)
        if total>MAX_ARCHIVE_BYTES:raise ValueError('archive bytes cap')
        event=json.loads(data);event_id=cap.sha(data)
        keys(event,('sequence','previous_sha256','registration_id','kind','committed_at','request','classification'))
        if data!=canonical_bytes(event) or path.name!=f'{seq:08d}_{event_id}.json' or event['sequence']!=seq or event['previous_sha256']!=head or event['registration_id']!=reg['registration_id']:raise ValueError('event chain/registration')
        marker_raw=cap.read(root/'publications'/(path.name+'.receipt'),4096);total+=len(marker_raw)
        marker=json.loads(marker_raw);keys(marker,('event_id','publication_completed_at'))
        timestamp=cap.time(marker['publication_completed_at'])
        if marker['event_id']!=event_id or timestamp<cap.time(event['committed_at']):raise ValueError('publication identity/clock reversal')
        if total>MAX_ARCHIVE_BYTES:raise ValueError('archive bytes cap')
        if last is not None and cap.time(event['committed_at'])<last:raise ValueError('archive clock reversal')
        if event['kind']=='observation':
            if event['request']['query_day'] in days:raise ValueError('duplicate cohort day')
            days.add(event['request']['query_day'])
            if event['classification']!=_provisional(_validate_observation(event,reg,root,cache)):raise ValueError('classification mismatch')
            if event['request']['attempt']!=event['request']['query_day']+'.json':raise ValueError('attempt path')
            attempt_raw=cap.read(root/'attempts'/event['request']['attempt'],MAX_EVENT_BYTES)
            if cap.sha(attempt_raw)!=event['request']['attempt_sha256']:raise ValueError('attempt hash')
            attempt=json.loads(attempt_raw)
            if attempt['query_day']!=event['request']['query_day'] or cap.time(attempt['started_at'])>cap.time(event['request']['issued_at']):raise ValueError('attempt identity')
            if any(timestamp>=cap.time(f['entry_at'])-timedelta(seconds=reg['cohort']['entry_observation_buffer_seconds']) for f in event['request']['forecasts']):raise ValueError('publication missed entry boundary')
            observations[event_id]=event['request']
        elif event['kind']=='resolution':
            if event['classification'] is not None:raise ValueError('resolution classification')
            key=_validate_resolution(event,observations,resolved,root,cache)
            resolved[key]=tuple(event['request'][k] for k in ('outcome','capture_id','closed_at'))
        else:raise ValueError('event kind')
        head,last=digest({'event_id':event_id,'publication_receipt_sha256':cap.sha(marker_raw)}),timestamp
    if {p.name for p in (root/'publications').iterdir()}!={p.name+'.receipt' for p in files}:raise ValueError('publication inventory')
    # Include all captures (also orphans from interrupted issue) in the raw budget.
    capture_bytes=0
    for directory in (root/'captures').iterdir():
        _capture(root,directory.name,cache)
        capture_bytes+=sum(cap.safe(p).stat().st_size for p in directory.iterdir())
    if capture_bytes>cap.MAX_CAPTURE_BYTES:raise ValueError('capture budget')
    attempts={}
    for path in (root/'attempts').iterdir():
        if path.name.endswith('.failure.json'):
            failure=json.loads(cap.read(path,4096));keys(failure,('error','error_sha256','status'))
            if failure['status']!='failed_no_reuse' or not (root/'attempts'/path.name.replace('.failure.json','.json')).is_file():raise ValueError('failure inventory')
            continue
        a=json.loads(cap.read(path,MAX_EVENT_BYTES));keys(a,('query_day','started_at','registration_id'))
        if path.name!=a['query_day']+'.json' or a['registration_id']!=reg['registration_id']:raise ValueError('attempt inventory')
        if a['query_day'] not in reg['cohort']['decision_days']:raise ValueError('attempt cohort')
        attempts[a['query_day']]=a
    if len(attempts)>MAX_EVENTS:raise ValueError('attempt cap')
    state_head,total,scientific_file_count=_persisted_head(root,head)
    if expected_head is not None and state_head!=expected_head:raise ValueError('trusted head mismatch')
    return {'head_sha256':state_head,'event_chain_head_sha256':head,'scientific_file_count':scientific_file_count,
            'event_count':len(files),'archive_bytes':total,'capture_bytes':capture_bytes,
            'observation_count':len(observations),'resolution_count':len(resolved),'pending_or_failed_days':sorted(set(attempts)-days)},reg,observations,resolved,last


def verify(root,expected_head=None):
    with lock(root,False) as root:return _read(root,expected_head)[0]


def _provisional(classification):
    return {k:v for k,v in classification.items() if k not in ('prospective_eligibility','classification')} | {'classification':'provisional_requires_publication_receipt'}


def _append(root,state,reg,kind,request,classification,commit):
    if state['event_count']>=MAX_EVENTS:raise ValueError('event cap')
    event={'sequence':state['event_count']+1,'previous_sha256':state['event_chain_head_sha256'],'registration_id':reg['registration_id'],
           'kind':kind,'committed_at':cap.stamp(commit),'request':request,'classification':_provisional(classification) if kind=='observation' else None}
    raw=canonical_bytes(event)
    current_bytes=state['archive_bytes']+(root/'attempts'/request['attempt']).stat().st_size if kind=='observation' else state['archive_bytes']
    if len(raw)>MAX_EVENT_BYTES or current_bytes+len(raw)+4096>MAX_ARCHIVE_BYTES:raise ValueError('event/archive byte cap')
    identity=cap.sha(raw);filename=f"{event['sequence']:08d}_{identity}.json"
    cap.frozen_write(root/'events'/filename,raw)
    completed=now()
    marker={'event_id':identity,'publication_completed_at':cap.stamp(completed)}
    marker_raw=canonical_bytes(marker)
    cap.frozen_write(root/'publications'/(filename+'.receipt'),marker_raw)
    if completed<commit or (kind=='observation' and any(completed>=cap.time(f['entry_at'])-timedelta(seconds=reg['cohort']['entry_observation_buffer_seconds']) for f in request['forecasts'])):
        raise ValueError('publication clock reversal/entry boundary; archive invalid, no eligibility')
    event_head=digest({'event_id':identity,'publication_receipt_sha256':cap.sha(marker_raw)})
    state_head,_,_=_persisted_head(root,event_head)
    return {'event_id':identity,'head_sha256':state_head,'event_chain_head_sha256':event_head,
            'committed_at':event['committed_at'],'publication_completed_at':cap.stamp(completed),'classification':classification}


def issue(root,capture_dirs,producer):
    """Execute the registered producer on owned bytes; never accept caller forecasts."""
    with lock(root) as root:
        state,reg,observations,resolved,last=_read(root)
        started=now();day=started.date().isoformat()
        if day not in reg['cohort']['decision_days'] or (last is not None and started<last):raise ValueError('wrong cohort day/clock reversal')
        attempt=root/'attempts'/(day+'.json')
        if attempt.exists():raise ValueError('cohort day already attempted')
        if not 1<=len(capture_dirs)<=MAX_PARENTS:raise ValueError('parent count')
        expected=reg['producer']
        if source_identity(producer,expected['code'])!=expected:raise ValueError('producer/code/runtime drift')
        cap.frozen_write(attempt,canonical_bytes({'query_day':day,'started_at':cap.stamp(started),'registration_id':reg['registration_id']}))
        try:
            captures=[_own_capture(root,p) for p in capture_dirs]
            if any(cap.time(c['completed_at'])>started for c in captures):raise ValueError('capture after issue start')
            raw=tuple(cap.verify_capture(root/'captures'/c['capture_id'])[0] for c in captures)
            config_raw=canonical_bytes(reg['config']);config=json.loads(config_raw)
            produced=producer(raw,config,day)
            issued=now()
            if issued<started or issued.date().isoformat()!=day:raise ValueError('issue clock reversal/midnight miss')
            if canonical_bytes(config)!=config_raw or source_identity(producer,expected['code'])!=expected:raise ValueError('producer/config changed during call')
            if cap.read(root/'registration.json',MAX_EVENT_BYTES)!=canonical_bytes(reg):raise ValueError('registration changed during call')
            produced=json.loads(canonical_bytes(produced));keys(produced,('selected','features','forecasts'))
            output_hash=digest(produced)
            for selected in produced['selected']:
                keys(selected,('capture_index','closed_at','prefix'));selected['prefix_sha256']=digest(selected['prefix'])
            for f in produced['forecasts']:
                keys(f,('model','interpretation','target','horizon_months','atoms','weights'))
                entry,end,available=label_calendar(issued,f['horizon_months'])
                f.update(entry_at=cap.stamp(entry),label_end_at=cap.stamp(end),label_available_at=cap.stamp(available))
            request={'attempt':attempt.name,'attempt_sha256':cap.sha(cap.read(attempt,MAX_EVENT_BYTES)),'query_day':day,'issued_at':cap.stamp(issued),'capture_ids':[c['capture_id'] for c in captures],
                     **produced,'producer_output_sha256':output_hash}
            commit=now()
            event={'request':request,'committed_at':cap.stamp(commit)}
            classification=_validate_observation(event,reg,root,{})
            return _append(root,state,reg,'observation',request,classification,commit)
        except Exception as error:
            failure=canonical_bytes({**cap.failure_evidence(error),'status':'failed_no_reuse'})
            if len(failure)>4096:raise ValueError('issue failure evidence byte cap') from error
            cap.frozen_write(root/'attempts'/(day+'.failure.json'),failure);raise


def resolve(root,observation_id,model,target,horizon_months,outcome,capture_dir,closed_at):
    with lock(root) as root:
        state,reg,observations,resolved,last=_read(root);capture=_own_capture(root,capture_dir);commit=now()
        if last is not None and commit<last:raise ValueError('resolution clock reversal')
        request={'observation_id':observation_id,'model':model,'target':target,'horizon_months':horizon_months,
                 'outcome':outcome,'capture_id':capture['capture_id'],'closed_at':closed_at}
        _validate_resolution({'request':request,'committed_at':cap.stamp(commit)},observations,resolved,root,{})
        return _append(root,state,reg,'resolution',request,None,commit)
