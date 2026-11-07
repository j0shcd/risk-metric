"""Finite shared direct-CDF campaign ledger; local cooperative coordination only.

CLI: create --bundle DIR --spec JSON --campaign DIR; submit --campaign DIR
--request JSON; status --campaign DIR; freeze --campaign DIR --attempts SLOT...;
release --campaign DIR --request JSON; abandon --campaign DIR --attempt SLOT
--reason TEXT. Every request file is read once.

Create spec: {global_budget: int, worker_budgets: {worker: int}, prior_exposure:
{parents: [campaign IDs], statement: nonempty str, outer_history_exposed: bool}}.
Submit request: {worker, candidate_csv, column, name, provenance, producer, config,
params: object}. Paths name files captured into the reserved slot before parsing.
The outer target hash is first bound in the reserved release request, before
opening source bytes; it is not precommitted at campaign creation. Comparison of
parsed development prices AND baseline components is exact; CSV rounding changes
fail closed rather than being silently tolerated.

Release request: {source, source_sha256, candidates: [{attempt, csv, csv_sha256,
producer, config, params}]}. All finalists must be present exactly once.

New directories do not restore an unseen holdout. Explicit exposure lineage is
required, but no local ledger proves researchers did not read public history or
bypass this workflow. Interrupted slots consume budgets; unresolved submissions
block freeze until explicitly abandoned with a reason; abandonment never restores
budget and late completion cannot overwrite it. A reserved outer release is consumed even after failure or a crash.
Reproduction of an existing outer packet is not another validation release.
Producer/config hashes attest only supplied artifacts: this wrapper does not
execute the producer, bind its imports/weights/data closure, prove CSV derivation,
or verify causal generation of future values. A changed outer suffix can pass
with the same development prefix and declared artifacts. Partial administrative
publication remains fail-closed and is reported explicitly; never reset budgets.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import io
import json
from pathlib import Path
import platform
import re
import numpy as np
import pandas as pd
from .indicator_trial import CUTOFF, run_trial
from .indicator_outer_replay import candidate_from_csv, run_replay, readable
from .market_dataset import canonical_bytes, digest, load_snapshot
from .market_information import baseline_candidates, PROTOCOL as READOUT_PROTOCOL
from .scorecard_artifacts import publish, safe_path, verify_packet, write_packet

MAX_BYTES = 16 * 1024 * 1024
MAX_BUNDLE_BYTES = 64 * 1024 * 1024
MAX_DAILY_ROWS = 10000
PROVENANCE_LIMITATION = ('Declared-artifact continuity only: producer is not executed; imports, weights and data closure, '
                        'CSV derivation and causal future-value generation are not verified. No security seal or unseen holdout.')
CODE_FILES = ('direct_cdf_campaign.py','indicator_trial.py','indicator_outer_replay.py',
              'market_information.py','market_dataset.py','market_scorecard.py',
              'distribution_readout.py','scorecard_artifacts.py')
PROTOCOL = {'id':'shared-direct-cdf-campaign-v1','readout':READOUT_PROTOCOL,
            'development_cutoff':CUTOFF,'horizons':[12,24,48],'mature_pool':24,
            'budget':'all reserved slots count; malformed, failed and interrupted included',
            'exposure':'historical reconstruction, never an unseen holdout'}

def sha(payload): return hashlib.sha256(payload).hexdigest()
def read_once(path):
    with Path(path).open('rb') as stream:
        payload = stream.read(MAX_BYTES+1)
    if len(payload)>MAX_BYTES: raise ValueError('input exceeds bounded byte limit')
    return payload

def code_hashes():
    return {name:sha(Path(__file__).with_name(name).read_bytes()) for name in CODE_FILES}
def runtime():
    return {'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__}
def owned(path, payload):
    publish(path,payload)
    path.chmod(0o400)

def bounded_snapshot(path):
    # Bound line count before the frozen loader allocates a daily reindex.
    payload=read_once(path)
    frame=pd.read_csv(io.BytesIO(payload),index_col=0)
    dates=pd.to_datetime(frame.index,errors='raise')
    if not len(dates) or len(dates)>MAX_DAILY_ROWS or (dates.max()-dates.min()).days>=MAX_DAILY_ROWS:
        raise ValueError('snapshot exceeds bounded date/row range')
    result=load_snapshot(path)
    if result['source_sha256']!=sha(payload): raise ValueError('owned source changed')
    return result

@contextmanager
def locked(target):
    target=safe_path(Path(target))
    with (target/'.lock').open('r+b') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX)
        try: yield target
        finally: fcntl.flock(stream,fcntl.LOCK_UN)

def slots(target):
    return sorted((target/'attempts').iterdir())

def terminal(slot):
    packets=[path for path in (slot,slot/'abandonment') if (path/'COMPLETE').exists()]
    if len(packets)>1: raise ValueError('conflicting terminal attempt receipts')
    if not packets: return None
    verify_packet(packets[0])
    result=json.loads((packets[0]/'outcome.json').read_bytes())
    if result['status']=='abandoned':
        for name,expected in result['interrupted_file_hashes'].items():
            if Path(name).name!=name or sha((slot/name).read_bytes())!=expected:
                raise ValueError('abandoned attempt evidence changed')
    return result

def verify(target):
    verify_packet(target)
    manifest=json.loads((target/'manifest.json').read_bytes())
    if manifest['protocol']!=PROTOCOL or manifest['code_hashes']!=code_hashes() or manifest['runtime']!=runtime():
        raise ValueError('campaign protocol/code/runtime identity changed')
    if manifest['campaign_id']!=digest({k:v for k,v in manifest.items() if k!='campaign_id'}):
        raise ValueError('campaign identity mismatch')
    verify_packet(target/'bundle')
    if sha((target/'bundle'/'receipt.json').read_bytes())!=manifest['bundle_receipt_sha256']:
        raise ValueError('campaign bundle identity mismatch')
    for slot in slots(target):
        if not re.fullmatch(r'attempt-\d{3}--[a-zA-Z0-9_-]{1,40}',slot.name) or not slot.is_dir():
            raise ValueError('invalid ledger slot')
        safe_path(slot)
        outcome=terminal(slot)
        if outcome is not None:
            if outcome['campaign_id']!=manifest['campaign_id'] or outcome['attempt']!=slot.name:
                raise ValueError('foreign attempt receipt')
    if (target/'freeze'/'COMPLETE').exists():
        verify_packet(target/'freeze')
        frozen=json.loads((target/'freeze'/'finalists.json').read_bytes())
        if frozen['campaign_id']!=manifest['campaign_id']: raise ValueError('foreign freeze receipt')
        for finalist in frozen['finalists']:
            if finalist['attempt'] not in {s.name for s in slots(target)}:
                raise ValueError('missing frozen attempt')
            if sha((target/'attempts'/finalist['attempt']/'receipt.json').read_bytes())!=finalist['attempt_receipt_sha256']:
                raise ValueError('frozen attempt receipt changed')
    if (target/'release'/'COMPLETE').exists():
        verify_packet(target/'release')
        result=json.loads((target/'release'/'outcome.json').read_bytes())
        if result['campaign_id']!=manifest['campaign_id'] or result['freeze_receipt_sha256']!=sha((target/'freeze'/'receipt.json').read_bytes()):
            raise ValueError('foreign release receipt')
    return manifest

def create_campaign(bundle, target, spec):
    if type(spec.get('global_budget')) is not int or not 1<=spec['global_budget']<=999:
        raise ValueError('global budget must be integer1..999')
    workers=spec.get('worker_budgets')
    if not isinstance(workers,dict) or not workers or any(not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}',w) or type(n) is not int or not 1<=n<=999 for w,n in workers.items()):
        raise ValueError('invalid worker budgets')
    exposure=spec.get('prior_exposure')
    if (not isinstance(exposure,dict) or not isinstance(exposure.get('parents'),list)
            or any(not isinstance(p,str) or not p.strip() for p in exposure['parents'])
            or not isinstance(exposure.get('statement'),str) or not exposure['statement'].strip()
            or type(exposure.get('outer_history_exposed')) is not bool):
        raise ValueError('explicit prior-exposure lineage required; a directory is not a fresh holdout')
    target=safe_path(Path(target));target.mkdir(exist_ok=False)
    (target/'.lock').touch();(target/'attempts').mkdir();(target/'bundle').mkdir()
    manifest_bytes=read_once(Path(bundle)/'manifest.json'); inputs=json.loads(manifest_bytes)
    if inputs['cutoff']!=CUTOFF or 'development_scores.csv' not in inputs['sources'] or len(inputs['sources'])>64:
        raise ValueError('invalid development bundle')
    payloads={'manifest.json':manifest_bytes}
    for name,info in inputs['sources'].items():
        if Path(name).name!=name or name in ('manifest.json','receipt.json','COMPLETE'):
            raise ValueError('unsafe bundle filename')
        payload=read_once(Path(bundle)/name)
        if sha(payload)!=info['development_sha256']: raise ValueError('bundle hash mismatch')
        payloads[name]=payload
        if sum(map(len,payloads.values()))>MAX_BUNDLE_BYTES: raise ValueError('bundle exceeds byte budget')
        # All declared CSV inputs, including warm-up sources, obey the cutoff.
        frame=pd.read_csv(io.BytesIO(payload))
        if len(frame)>MAX_DAILY_ROWS: raise ValueError('input exceeds row budget')
        if len(frame):
            dates=pd.to_datetime(frame['Date'] if 'Date' in frame else frame.iloc[:,0],errors='raise')
            if dates.isna().any() or dates.max()>pd.Timestamp(CUTOFF): raise ValueError('post-cutoff or invalid development input')
    write_packet(target/'bundle',payloads)
    for file in (target/'bundle').iterdir(): file.chmod(0o400)
    snapshot=bounded_snapshot(target/'bundle'/'development_scores.csv')
    references=baseline_candidates(snapshot)
    manifest={'protocol':PROTOCOL,'code_hashes':code_hashes(),'runtime':runtime(),
              'global_budget':spec['global_budget'],'worker_budgets':workers,'prior_exposure':exposure,
              'bundle_receipt_sha256':sha((target/'bundle'/'receipt.json').read_bytes()),
              'source_sha256':snapshot['source_sha256'],'references_id':digest(references),
              'support':[r['date'] for r in snapshot['monthly']]}
    manifest['campaign_id']=digest(manifest)
    write_packet(target,{'manifest.json':canonical_bytes(manifest),'references.json':canonical_bytes(references)})
    return manifest

def state(target):
    if (target/'release').exists():
        if (target/'release'/'COMPLETE').exists():
            verify_packet(target/'release')
            result=json.loads((target/'release'/'outcome.json').read_bytes())
            if result['status']=='completed':
                verify_packet(target/'release'/'packet')
                if sha((target/'release'/'packet'/'receipt.json').read_bytes())!=result['packet_receipt_sha256']:
                    raise ValueError('outer packet identity mismatch')
                return 'RELEASE_COMPLETE'
        return 'RELEASE_RESERVED'
    if (target/'freeze').exists():
        return 'FROZEN' if (target/'freeze'/'COMPLETE').exists() else 'FREEZE_RESERVED'
    return 'OPEN'

def status(target):
    with locked(target) as target:
        manifest=verify(target)
        attempts=[]
        for slot in slots(target):
            result=terminal(slot) or {'status':'reserved_or_interrupted'}
            attempts.append({'attempt':slot.name,'worker':slot.name.split('--',1)[1],'status':result['status']})
        release_status='not_reserved'
        if (target/'release').exists():
            release_status=(json.loads((target/'release'/'outcome.json').read_bytes())['status']
                            if (target/'release'/'COMPLETE').exists() else 'reserved_or_interrupted')
        return {'campaign_id':manifest['campaign_id'],'state':state(target),'attempts':attempts,
                'release_status':release_status,'prior_exposure':manifest['prior_exposure']}

def submit(target, request):
    with locked(target) as target:
        manifest=verify(target)
        if state(target)!='OPEN': raise ValueError('development is closed')
        worker=request.get('worker')
        if worker not in manifest['worker_budgets']: raise ValueError('unknown worker')
        existing=slots(target)
        if len(existing)>=manifest['global_budget'] or sum(s.name.split('--',1)[1]==worker for s in existing)>=manifest['worker_budgets'][worker]:
            raise ValueError('attempt budget exhausted; failures and interruptions count')
        slot=target/'attempts'/f'attempt-{len(existing)+1:03d}--{worker}'
        slot.mkdir(exist_ok=False)  # Name alone reserves both budgets, even if process dies next.
        request_bytes=canonical_bytes(request)
        owned(slot/'request.json',request_bytes)
        request=json.loads(request_bytes)
    bound=['request.json']
    try:
        if not isinstance(request.get('params'),dict): raise ValueError('parameters must be explicit object')
        files={'candidate.csv':read_once(request['candidate_csv']),'producer.bin':read_once(request['producer']),
               'config.bin':read_once(request['config']),'params.json':canonical_bytes(request['params'])}
        identity={'producer_sha256':sha(files['producer.bin']),'config_sha256':sha(files['config.bin']),
                  'params_sha256':sha(files['params.json'])}
        with locked(target):
            verify(target)
            completed=terminal(slot)
            if completed is not None: return completed
            if state(target)!='OPEN': raise ValueError('campaign closed during input capture')
            for name,payload in files.items(): owned(slot/name,payload);bound.append(name)
        trial=run_trial(target/'bundle',slot/'candidate.csv',request['column'],request['name'],request['provenance'])
        outcome={'status':'completed','identity':identity,'candidate':trial['candidate']}
        payloads={'trial.json':canonical_bytes(trial)}
    except Exception as error:
        outcome={'status':'failed','reason':str(error)};payloads={}
    outcome.update({'campaign_id':manifest['campaign_id'],'attempt':slot.name})
    with locked(target):
        verify(target)
        completed=terminal(slot)
        if completed is not None: return completed
        if state(target)!='OPEN': raise ValueError('campaign closed during attempt')
        write_packet(slot,{**payloads,'outcome.json':canonical_bytes(outcome)},bound_existing=tuple(bound))
    return outcome

def abandon(target, attempt, reason):
    """Seal an interrupted reservation without reclaiming its budget or overwriting completion."""
    if not isinstance(reason,str) or not reason.strip(): raise ValueError('abandonment requires a reason')
    with locked(target) as target:
        manifest=verify(target)
        existing={s.name:s for s in slots(target)}
        if attempt not in existing: raise ValueError('unknown campaign attempt')
        slot=existing[attempt]
        completed=terminal(slot)
        if completed is not None: return completed
        if state(target)!='OPEN': raise ValueError('cannot abandon after campaign closure')
        # Preserve even an interrupted primary receipt; never overwrite its files.
        existing_files={name:sha((slot/name).read_bytes()) for name in
                        ('request.json','candidate.csv','producer.bin','config.bin','params.json','trial.json','outcome.json','receipt.json')
                        if (slot/name).exists()}
        outcome={'status':'abandoned','reason':reason.strip(),'campaign_id':manifest['campaign_id'],'attempt':attempt,
                 'interrupted_file_hashes':existing_files}
        (slot/'abandonment').mkdir(exist_ok=False)
        write_packet(slot/'abandonment',{'outcome.json':canonical_bytes(outcome)})
        return outcome

def freeze(target, selected):
    with locked(target) as target:
        manifest=verify(target)
        if state(target)!='OPEN': raise ValueError('campaign already closed')
        existing={s.name:s for s in slots(target)}
        if any(terminal(s) is None for s in existing.values()): raise ValueError('unresolved reserved/interrupted attempts block freeze')
        if not selected or len(set(selected))!=len(selected) or any(s not in existing for s in selected):
            raise ValueError('select unique successful campaign attempts')
        finalists=[]
        for name in sorted(selected):
            slot=existing[name];outcome=terminal(slot)
            if outcome['status']!='completed': raise ValueError('finalist must be a successful attempt')
            finalists.append({'attempt':name,'attempt_receipt_sha256':sha((slot/'receipt.json').read_bytes()),
                              'identity':outcome['identity'],'candidate':outcome['candidate'],
                              'request':json.loads((slot/'request.json').read_bytes())})
        if len({f['candidate']['name'] for f in finalists})!=len(finalists):
            raise ValueError('finalist names must be unique')
        packet={'campaign_id':manifest['campaign_id'],'finalists':finalists}
        (target/'freeze').mkdir(exist_ok=False)
        write_packet(target/'freeze',{'finalists.json':canonical_bytes(packet)})
        return packet

def release(target, request):
    with locked(target) as target:
        manifest=verify(target)
        if state(target)!='FROZEN': raise ValueError('one outer release requires frozen campaign; reservations are consumed')
        verify_packet(target/'freeze')
        frozen=json.loads((target/'freeze'/'finalists.json').read_bytes())
        if frozen['campaign_id']!=manifest['campaign_id']: raise ValueError('foreign finalists')
        release_dir=target/'release';release_dir.mkdir(exist_ok=False)
        request_bytes=canonical_bytes(request)
        owned(release_dir/'request.json',request_bytes)  # Before reading any outer input.
        request=json.loads(request_bytes)
    bound=['request.json']
    try:
        supplied=request['candidates']
        if not isinstance(supplied,list) or len(supplied)!=len(frozen['finalists']) or {c['attempt'] for c in supplied}!={c['attempt'] for c in frozen['finalists']}:
            raise ValueError('outer release must contain exact frozen finalist set')
        source=read_once(request['source'])
        if sha(source)!=request['source_sha256']: raise ValueError('declared outer source hash mismatch')
        owned(release_dir/'outer_source.csv',source);bound.append('outer_source.csv')
        snapshot=bounded_snapshot(release_dir/'outer_source.csv')
        development=bounded_snapshot(target/'bundle'/'development_scores.csv')
        if [r for r in snapshot['daily'] if r['date']<=development['daily'][-1]['date']]!=development['daily']:
            raise ValueError('outer source revises development price history')
        if [r for r in snapshot['monthly'] if r['date']<=manifest['support'][-1]]!=development['monthly']:
            raise ValueError('outer source revises development baseline/component history')
        registration={'source_sha256':sha(source),'candidates':[]}
        for i,finalist in enumerate(frozen['finalists']):
            slot=target/'attempts'/finalist['attempt'];verify_packet(slot)
            if sha((slot/'receipt.json').read_bytes())!=finalist['attempt_receipt_sha256']:
                raise ValueError('frozen attempt identity changed')
            declaration=next(c for c in supplied if c['attempt']==finalist['attempt'])
            producer=read_once(declaration['producer']);config=read_once(declaration['config']);params=canonical_bytes(declaration['params'])
            identity={'producer_sha256':sha(producer),'config_sha256':sha(config),'params_sha256':sha(params)}
            if identity!=finalist['identity']: raise ValueError('producer/config/parameters changed after freeze')
            csv=read_once(declaration['csv'])
            if sha(csv)!=declaration['csv_sha256']: raise ValueError('declared outer candidate hash mismatch')
            descriptor={'name':finalist['candidate']['name'],'column':finalist['request']['column'],
                        'direction':finalist['candidate']['direction'],'provenance':finalist['candidate']['provenance']}
            candidate=candidate_from_csv(csv,descriptor,snapshot)
            prefix=[r for r in candidate['values'] if r['date']<=manifest['support'][-1]]
            if prefix!=finalist['candidate']['values']: raise ValueError('outer candidate development prefix mismatch')
            files={f'full_candidate_{i}.csv':csv,f'producer_{i}.bin':producer,f'config_{i}.bin':config,
                   f'params_{i}.json':params,f'finalist_{i}.json':canonical_bytes(finalist)}
            for name,payload in files.items(): owned(release_dir/name,payload);bound.append(name)
            registration['candidates'].append({**descriptor,'csv':f'full_candidate_{i}.csv','csv_sha256':sha(csv),
                                               'manifest':f'finalist_{i}.json','manifest_sha256':sha(files[f'finalist_{i}.json']),'frozen':True})
        owned(release_dir/'owned_registration.json',canonical_bytes(registration));bound.append('owned_registration.json')
        replay,files=run_replay(release_dir/'outer_source.csv',release_dir/'owned_registration.json')
        (release_dir/'packet').mkdir()
        write_packet(release_dir/'packet',{**files,'replay.json':canonical_bytes(replay),'report.md':readable(replay)})
        outcome={'status':'completed','packet_receipt_sha256':sha((release_dir/'packet'/'receipt.json').read_bytes())}
    except Exception as error:
        outcome={'status':'failed','reason':str(error),'release_consumed':True}
    outcome.update({'campaign_id':manifest['campaign_id'],'freeze_receipt_sha256':sha((target/'freeze'/'receipt.json').read_bytes()),
                    'limitations':[PROVENANCE_LIMITATION]})
    with locked(target):
        verify(target)
        write_packet(release_dir,{'outcome.json':canonical_bytes(outcome)},bound_existing=tuple(bound))
    return outcome

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['create','submit','status','freeze','release','abandon'])
    p.add_argument('--campaign',type=Path,required=True);p.add_argument('--bundle',type=Path);p.add_argument('--spec',type=Path)
    p.add_argument('--request',type=Path);p.add_argument('--attempts',nargs='+')
    p.add_argument('--attempt');p.add_argument('--reason');a=p.parse_args()
    if a.command=='create': result=create_campaign(a.bundle,a.campaign,json.loads(read_once(a.spec)))
    elif a.command=='submit': result=submit(a.campaign,json.loads(read_once(a.request)))
    elif a.command=='freeze': result=freeze(a.campaign,a.attempts)
    elif a.command=='release': result=release(a.campaign,json.loads(read_once(a.request)))
    elif a.command=='abandon': result=abandon(a.campaign,a.attempt,a.reason)
    else: result=status(a.campaign)
    print(json.dumps(result))

if __name__=='__main__': main()
