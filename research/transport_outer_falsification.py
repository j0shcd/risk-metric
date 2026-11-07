"""One postselected chronological falsification; unchanged transport kernel.

Register hashes only, then separately run after root review. No generative outer
extension, decoder search, old-origin challenge pooling, or automatic promotion.
Input bytes are captured once, including complete parent receipts. Success and
failure packets are exclusive and bind captured registration and inputs.
"""
from __future__ import annotations
import argparse
import io
import json
from pathlib import Path
import platform
import tempfile
import numpy as np
import pandas as pd
from .return_transport import transport, PROTOCOL as KERNEL_PROTOCOL
from .market_dataset import build_dataset, load_snapshot, canonical_bytes, digest
from .market_information import PROTOCOL as CDF_PROTOCOL
from .benchmark_frontier import DIRECT_NAMES
from .readout_study import diagnostics
from .scorecard_artifacts import publish, safe_path, write_packet
import hashlib

ROOT=Path(__file__).resolve().parents[1]
KERNEL_SHA256='ca97bba48a54af710f31b2a7e1086f0b07349d68222f66fe95a000eff12adee0'
MODELS=('intercept','context','context+time_years_since_2012')
METRICS=('crps','brier','coverage_50','coverage_80','width_50','width_80','outside_atom_range')
PROTOCOL={'id':'transport-outer-falsification-v1','kernel_sha256':KERNEL_SHA256,
          'models':list(MODELS),'horizons':[12,24],'primary':'24-month terminal_log_return',
          'outer_start':'2023-01-01','development_cutoff':'2022-12-31',
          'outer_counts':{'12':30,'24':18},'development_counts':{'12':48,'24':24},
          'full_months':139,'development_months':97,'training_n':24,
          'training':'latest24 labels strictly available before query; unchanged rank/ridge24/PRESS',
          'frontier':'13 fixed issued CDFs plus context/unconditional; both generative replicas unavailable',
          'stopping':'age CRPS>=context at24m: incremental contribution fails; age CRPS>=unconditional at24m: benchmark improvement fails; mixed metrics remain mixed',
          'exposure':'postselected after23 models and primary-target inspection; outer history already exposed, not fresh holdout',
          'interpretation':'age ranks model rolling mature-label chronology, not BTC maturation; no significance, tuning or promotion'}
MAX_BYTES=64*1024*1024
MAX_TOTAL=256*1024*1024

def sha(raw):return hashlib.sha256(raw).hexdigest()
def bounded(path):
    with Path(path).open('rb') as stream:raw=stream.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:raise ValueError('input byte limit')
    return raw

def identity():
    if sha((ROOT/'research/return_transport.py').read_bytes())!=KERNEL_SHA256:
        raise ValueError('accepted transport kernel changed')
    return {'protocol':PROTOCOL,'code':{str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sorted((ROOT/'research').rglob('*.py'))},
            'runtime':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__}}

def build_registration(snapshot,development,prior_packet,reference_packet):
    paths={'snapshot':Path(snapshot),'development':Path(development)}
    for role,packet in (('prior',Path(prior_packet)),('references',Path(reference_packet))):
        receipt=json.loads(bounded(packet/'receipt.json'))
        if 'COMPLETE' not in receipt['files']:raise ValueError('incomplete parent receipt')
        paths[role+':receipt.json']=packet/'receipt.json'
        for name in receipt['files']:
            if Path(name).name!=name:raise ValueError('unsafe parent name')
            paths[role+':'+name]=packet/name
    reg=identity();reg['inputs']={name:{'path':str(path.resolve()),'sha256':sha(bounded(path))} for name,path in paths.items()}
    reg['registration_id']=digest(reg);return reg

def capture(reg,on_read=None):
    expected=identity()
    if any(reg.get(k)!=v for k,v in expected.items()) or reg.get('registration_id')!=digest({k:v for k,v in reg.items() if k!='registration_id'}):
        raise ValueError('registration/code/runtime identity mismatch')
    payload={};total=0
    for name,info in reg['inputs'].items():
        raw=bounded(info['path']);total+=len(raw)
        if total>MAX_TOTAL:raise ValueError('registered input size mismatch')
        if on_read is not None:on_read(name,raw)
        if sha(raw)!=info['sha256']:raise ValueError('registered input identity mismatch')
        payload[name]=raw
    for role in ('prior','references'):
        receipt=json.loads(payload[role+':receipt.json'])
        if 'COMPLETE' not in receipt['files']:raise ValueError('incomplete parent')
        for name,h in receipt['files'].items():
            if Path(name).name!=name or sha(payload[role+':'+name])!=h:raise ValueError('corrupt parent receipt')
    return payload

def prepared(snapshot):
    rows=build_dataset(snapshot,[12,24])['rows']
    context=np.array([r['context'] for r in rows],float)
    if context.shape!=(len(rows),2) or not np.isfinite(context).all():raise ValueError('common finite context required')
    age=np.array([(pd.Timestamp(r['date'])-pd.Timestamp('2012-01-01')).days/365.2425 for r in rows])
    return rows,{'intercept':np.empty((len(rows),0)),'context':context,MODELS[2]:np.column_stack([context,age])}

def pool(rows,i,h):
    return [j for j in range(i) if rows[j]['outcomes'][str(h)]['status']=='complete' and rows[j]['outcomes'][str(h)]['available']<rows[i]['date']][-24:]

def forecast(rows,features,i,h,name,role):
    row=rows[i];target=row['outcomes'][str(h)];mature=pool(rows,i,h)
    if len(mature)!=24:raise ValueError('insufficient mature pool')
    y=np.array([rows[j]['outcomes'][str(h)]['values'][0] for j in mature])
    prediction=transport(features[name][mature],features[name][i],y)
    return {'date':row['date'],'horizon':h,'target':'terminal_log_return','role':role,
            'outcome':target['values'][0],'entry':target['entry'],'end':target['end'],'label_available':target['available'],
            'model':name,'status':'scored',**prediction,
            **diagnostics(np.array(prediction['atoms']),np.full(24,1/24),target['values'][0],'terminal_log_return'),
            'train_dates':[rows[j]['date'] for j in mature]}

def validate_inputs(payload):
    snapshot=json.loads(payload['snapshot'])
    with tempfile.TemporaryDirectory(prefix='outer-development-capture-') as tmp:
        p=Path(tmp)/'source.csv';p.write_bytes(payload['development']);development=load_snapshot(p)
    if (development['daily'][-1]['date']!=PROTOCOL['development_cutoff']
            or len(snapshot['monthly'])!=139 or len(development['monthly'])!=97
            or [r for r in snapshot['daily'] if r['date']<=PROTOCOL['development_cutoff']]!=development['daily']
            or [r for r in snapshot['monthly'] if r['date']<=PROTOCOL['development_cutoff']]!=development['monthly']):
        raise ValueError('full snapshot revises development prefix/support')
    prior=json.loads(payload['prior:study.json']);prior_reg=json.loads(payload['prior:registration.json'])
    if (prior_reg['registration_id']!=digest({k:v for k,v in prior_reg.items() if k!='registration_id'})
            or prior['registration_id']!=prior_reg['registration_id'] or prior['protocol']!=KERNEL_PROTOCOL
            or prior_reg['protocol']!=KERNEL_PROTOCOL or prior_reg['inputs']['source']['sha256']!=sha(payload['development'])
            or prior_reg['code']['research/return_transport.py']!=KERNEL_SHA256):
        raise ValueError('prior study/source/kernel identity mismatch')
    current_code=identity()['code']
    if len(prior_reg['code'])!=43 or any(current_code.get(name)!=h for name,h in prior_reg['code'].items()):
        raise ValueError('prior recorded code changed; new wrapper may extend closure only')
    if prior_reg['runtime']!=identity()['runtime']:raise ValueError('prior runtime mismatch')
    replay=json.loads(payload['references:replay.json']);refs=replay['references']
    if replay['source_sha256']!=snapshot['source_sha256'] or {r['candidate_name'] for r in refs}!=set(DIRECT_NAMES) or len(refs)!=13:
        raise ValueError('fixed CDF family/source mismatch')
    data_id=digest(build_dataset(snapshot,[12,24,48]));snapshot_id=digest(snapshot)
    expected_code={name:sha((ROOT/'research'/name).read_bytes()) for name in ('market_information.py','market_dataset.py','market_scorecard.py','distribution_readout.py')}
    for ref in refs:
        if (ref['source_sha256']!=snapshot['source_sha256'] or ref['dataset_id']!=data_id or ref['snapshot_id']!=snapshot_id
                or ref['protocol']!=CDF_PROTOCOL or ref['minimum_training']!=24 or ref['as_of']!=snapshot['daily'][-1]['date']
                or ref['development_cutoff']!='2022-12-31' or ref['outer_start']!='2023-01-01' or ref['code_sha256']!=expected_code):
            raise ValueError('CDF protocol/dataset/source identity mismatch')
    return snapshot,prior,refs

def nonoverlap(records):
    last='';n=0
    for r in sorted(records,key=lambda r:(r['end'],r['entry'])):
        if r['entry']>last:n+=1;last=r['end']
    return n

def reference_forecasts(rows,refs,outer):
    bydate={r['date']:i for i,r in enumerate(rows)}
    reference_maps={};support={(r['date'],r['horizon']) for r in outer}
    for ref in refs:
        selected=[r for r in ref['predictions'] if r['role']=='outer' and r['target']=='terminal_log_return' and r['horizon'] in (12,24)]
        mapping={(r['date'],r['horizon']):r for r in selected}
        # Unmatured reference origins may be present; they are not scored support.
        mapping={k:r for k,r in mapping.items() if r['outcome'] is not None}
        if len(selected)!=len({(r['date'],r['horizon']) for r in selected}) or set(mapping)!=support:raise ValueError('reference outer support mismatch')
        reference_maps['direct_cdf:'+ref['candidate_name']]=mapping
    first=next(iter(reference_maps.values()));reference_maps.update(unconditional=first,context_cdf=first)
    reference_records=[]
    for refname,mapping in reference_maps.items():
        for r in outer:
            p=mapping[r['date'],r['horizon']]
            if any(p[k]!=r[k] for k in ('outcome','entry','end','label_available','role')):raise ValueError('reference outcome mismatch')
            i=bydate[r['date']];mature=pool(rows,i,r['horizon']);atoms=[rows[j]['outcomes'][str(r['horizon'])]['values'][0] for j in mature]
            if p['train_dates']!=[rows[j]['date'] for j in mature] or p['atoms']!=atoms:raise ValueError('reference mature atoms mismatch')
            weights=np.full(24,1/24) if refname=='unconditional' else np.array(p['reference_weights'] if refname=='context_cdf' else p['candidate_weights'])
            scored={k:r[k] for k in ('date','horizon','target','role','outcome','entry','end','label_available')}
            scored.update({'model':refname,'status':'scored',**diagnostics(np.array(atoms),weights,r['outcome'],'terminal_log_return')})
            score_key='unconditional_crps' if refname=='unconditional' else 'reference_crps' if refname=='context_cdf' else 'candidate_crps'
            if not np.isclose(scored['crps'],p[score_key],rtol=0,atol=1e-12):raise ValueError('frozen reference loss mismatch')
            reference_records.append(scored)
    return reference_maps,reference_records

def evaluate(payload):
    snapshot,prior,refs=validate_inputs(payload);rows,features=prepared(snapshot);bydate={r['date']:i for i,r in enumerate(rows)}
    outer=[]
    for row in rows:
        if row['date']<PROTOCOL['outer_start']:continue
        for h in (12,24):
            target=row['outcomes'][str(h)]
            if target['status']=='complete' and target['available']<=snapshot['daily'][-1]['date']:
                outer.append({'date':row['date'],'horizon':h,'target':'terminal_log_return','role':'outer',
                              'outcome':target['values'][0],'entry':target['entry'],'end':target['end'],'label_available':target['available']})
    if any(sum(r['horizon']==h for r in outer)!=PROTOCOL['outer_counts'][str(h)] for h in (12,24)):
        raise ValueError('fixed outer support mismatch')
    reference_maps,reference_records=reference_forecasts(rows,refs,outer)
    old=[r for r in prior['records'] if r['model'] in MODELS]
    if len(old)!=216 or len({(r['model'],r['date'],r['horizon']) for r in old})!=216:raise ValueError('prior forecast inventory mismatch')
    checked=[]
    for r in old:
        if (r['role']!='development' or r['label_available']>'2022-12-31' or r['horizon'] not in (12,24)):
            raise ValueError('prior contains nondevelopment forecast')
        reproduced=forecast(rows,features,bydate[r['date']],r['horizon'],r['model'],'development')
        if any(r[k]!=v for k,v in reproduced.items()):raise ValueError('previously issued development forecast changed')
        checked.append(reproduced)
    for name in MODELS:
        for h in (12,24):
            if sum(r['model']==name and r['horizon']==h for r in old)!=PROTOCOL['development_counts'][str(h)]:raise ValueError('prior support mismatch')
    records=[]
    for i,row in enumerate(rows):
        if row['date']<PROTOCOL['outer_start']:continue
        for h in (12,24):
            target=row['outcomes'][str(h)]
            if target['status']!='complete' or target['available']>snapshot['daily'][-1]['date']:continue
            for name in MODELS:records.append(forecast(rows,features,i,h,name,'outer'))
    groups={(name,h):[r for r in records if r['model']==name and r['horizon']==h] for name in MODELS for h in (12,24)}
    if any(len(rr)!=PROTOCOL['outer_counts'][str(h)] for (name,h),rr in groups.items()):raise ValueError('fixed outer support mismatch')
    cells=[]
    for (name,h),rr in groups.items():
        for comparator in [*MODELS,*reference_maps]:
            peer=groups[comparator,h] if comparator in MODELS else [r for r in reference_records if r['model']==comparator and r['horizon']==h]
            paired={r['date']:r for r in peer}
            if set(paired)!={r['date'] for r in rr}:raise ValueError('paired support differs')
            cells.append({'model':name,'horizon':h,'reference':comparator,'n':len(rr),'origins_id':digest([r['date'] for r in rr]),
                          'means':{m:float(np.mean([r[m] for r in rr])) for m in METRICS},
                          'reference_minus_model':{m:float(np.mean([paired[r['date']][m]-r[m] for r in rr])) for m in METRICS}})
    classes=[]
    for h in (12,24):
        rr=groups['intercept',h];events=[r for r in rr if r['event_occurred']];others=[r for r in rr if not r['event_occurred']]
        classes.append({'horizon':h,'n':len(rr),'negative_return_n':len(events),'nonnegative_return_n':len(others),
                        'nonoverlap_total_n':nonoverlap(rr),'nonoverlap_negative_n':nonoverlap(events),'nonoverlap_nonnegative_n':nonoverlap(others),
                        'training_negative_counts':[sum(rows[j]['outcomes'][str(h)]['values'][0]<0 for j in pool(rows,bydate[r['date']],h)) for r in rr],
                        'interpretation':'classwise/era-wise nonoverlap counts are not additive or independent; single-class discrimination not established'})
    age=[c for c in cells if c['model']==MODELS[2] and c['horizon']==24]
    gains={c['reference']:c['reference_minus_model']['crps'] for c in age}
    return {'protocol':PROTOCOL,'status':'postselected_falsification_no_promotion','records':records,'reference_records':reference_records,
            'cells':cells,'class_support':classes,'development_prefix':{'verified_forecasts':len(checked),'forecast_digest':digest(checked)},
            'generative_outer':[{'replica':r,'status':'unavailable_not_computed','comparison':None} for r in (0,1)],
            'stopping':{'incremental_contribution_fails':gains['context']<=0,
                        'unconditional_benchmark_improvement_fails':gains['unconditional']<=0,
                        'interpretation':'descriptive stopping checks only; absence of failure is not acceptance; mixed metrics remain mixed'},
            'as_of':snapshot['daily'][-1]['date'],'source_sha256':snapshot['source_sha256']}

def run(registration_path,output):
    raw=bounded(registration_path);output=safe_path(Path(output));output.mkdir(parents=True,exist_ok=False)
    publish(output/'registration.json',raw);bound=['registration.json'];inventory={}
    def archive(role,data):
        name=f'input_{len(inventory):03d}.bin';publish(output/name,data);bound.append(name)
        inventory[role]={'file':name,'sha256':sha(data)}
    try:
        reg=json.loads(raw);payload=capture(reg,on_read=archive)
        publish(output/'inputs.json',canonical_bytes(inventory));bound.append('inputs.json')
        result=evaluate(payload);result['registration_id']=reg['registration_id']
        write_packet(output,{'result.json':canonical_bytes(result)},bound_existing=tuple(bound));return result
    except Exception as error:
        if inventory and 'inputs.json' not in bound:
            publish(output/'inputs.json',canonical_bytes(inventory));bound.append('inputs.json')
        if not (output/'receipt.json').exists():write_packet(output,{'error.json':canonical_bytes({'status':'failed_no_retuning','error':str(error)})},bound_existing=tuple(bound))
        raise

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    register=sub.add_parser('register');register.add_argument('--snapshot',type=Path,required=True);register.add_argument('--development',type=Path,required=True)
    register.add_argument('--prior-packet',type=Path,required=True);register.add_argument('--reference-packet',type=Path,required=True);register.add_argument('--output',type=Path,required=True)
    replay=sub.add_parser('run');replay.add_argument('--registration',type=Path,required=True);replay.add_argument('--output',type=Path,required=True)
    args=p.parse_args(argv)
    if args.command=='register':publish(args.output,canonical_bytes(build_registration(args.snapshot,args.development,args.prior_packet,args.reference_packet)))
    else:run(args.registration,args.output)

if __name__=='__main__':main()
