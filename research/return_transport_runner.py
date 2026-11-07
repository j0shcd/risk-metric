"""Exclusive registered runner for the fixed return-transport diagnostic.

Registration only hashes artifacts. Run parses captured bytes and is authorized
separately; no command implicitly fits while constructing registration.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
import tempfile
import zipfile
import pandas as pd
import numpy as np
from . import return_transport as model
from .market_dataset import canonical_bytes, load_snapshot, digest
from .scorecard_artifacts import publish, safe_path, write_packet

ARMS = (
 ('swing_a_memory_0','research/candidates/swing_a/development_trials.zip','trial_1/trial.json',None),
 ('swing_b_adaptive','research/candidates/swing_b/development_trials.zip','trial_1/trial.json',None),
 ('upside_energy_24m','research/candidates/swing_c/development_trial.zip','trial.json',None),
 ('monetary_risk','output/divergent-campaign-v2-2026-11-07/attempts/attempt-001--astra_c/candidate.csv',None,'monetary_risk'),
 ('attention_surge_risk','output/divergent-campaign-v2-2026-11-07/attempts/attempt-002--astra_a/candidate.csv',None,'attention_surge_risk'),
 ('astra_b_upside_concentration','output/divergent-campaign-v2-2026-11-07/attempts/attempt-003--astra_b/candidate.csv',None,'astra_b_upside_concentration'))
MAX_BYTES=64*1024*1024


def bounded(path):
    with Path(path).open('rb') as stream:raw=stream.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:raise ValueError('input byte limit')
    return raw


def build_registration(root,bundle,atlas):
    paths={'source':Path(bundle)/'development_scores.csv','manifest':Path(bundle)/'manifest.json','atlas':Path(atlas)}
    for name,relative,member,column in ARMS:
        p=Path(root)/relative;paths[name]=p
        if member is None:
            paths[name+':receipt']=p.parent/'receipt.json'
            # Bind all receipt-listed parent artifacts without parsing trial outcomes.
            receipt=json.loads(bounded(p.parent/'receipt.json'))
            for filename in receipt['files']:
                if Path(filename).name!=filename:raise ValueError('unsafe parent receipt')
                paths[name+':parent:'+filename]=p.parent/filename
    result=model.registration(paths)
    result['arms']=[{'name':n,'member':m,'column':c} for n,_,m,c in ARMS]
    result['registration_id']=digest({k:v for k,v in result.items() if k!='registration_id'})
    return result


def capture(registered):
    if registered['protocol']!=model.PROTOCOL or registered['arms']!=[{'name':n,'member':m,'column':c} for n,_,m,c in ARMS]:raise ValueError('protocol/inventory mismatch')
    expected_id=digest({k:v for k,v in registered.items() if k!='registration_id'})
    if registered['registration_id']!=expected_id:raise ValueError('registration digest mismatch')
    identity=model.registration({})
    if any(registered[k]!=identity[k] for k in ('code','runtime')):raise ValueError('code/runtime drift')
    payloads={name:bounded(value['path']) for name,value in registered['inputs'].items()}
    if any(hashlib.sha256(raw).hexdigest()!=registered['inputs'][name]['sha256'] for name,raw in payloads.items()):raise ValueError('input drift')
    return payloads


def zip_candidate(raw,member):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if len(archive.namelist())!=len(set(archive.namelist())) or len(archive.namelist())>200:raise ValueError('invalid ZIP inventory')
        if sum(i.file_size for i in archive.infolist())>MAX_BYTES:raise ValueError('ZIP expansion limit')
        prefix=str(Path(member).parent);prefix='' if prefix=='.' else prefix+'/'
        receipt=json.loads(archive.read(prefix+'receipt.json'))
        if 'COMPLETE' not in receipt['files'] or Path(member).name not in receipt['files']:raise ValueError('unbound parent candidate')
        for name,expected in receipt['files'].items():
            if Path(name).name!=name:raise ValueError('unsafe ZIP receipt')
            if hashlib.sha256(archive.read(prefix+name)).hexdigest()!=expected:raise ValueError('corrupt ZIP parent receipt')
        return json.loads(archive.read(member))['candidate']


def inputs(payloads):
    manifest=json.loads(payloads['manifest'])
    if manifest['cutoff']!='2022-12-31' or manifest['sources']['development_scores.csv']['development_sha256']!=hashlib.sha256(payloads['source']).hexdigest():raise ValueError('bundle mismatch')
    with tempfile.TemporaryDirectory(prefix='transport-capture-') as tmp:
        p=Path(tmp)/'source.csv';p.write_bytes(payloads['source']);snapshot=load_snapshot(p)
    dates=[r['date'] for r in snapshot['monthly']]
    if len(dates)!=97 or dates[0]!='2014-12-31' or dates[-1]!='2022-12-31':raise ValueError('common date support mismatch')
    candidates=[];availability=None
    for name,_,member,column in ARMS:
        if member:
            candidate=zip_candidate(payloads[name],member)
            if candidate['name']!=name:raise ValueError('old candidate identity mismatch')
        else:
            receipt=json.loads(payloads[name+':receipt'])
            if 'COMPLETE' not in receipt['files'] or 'candidate.csv' not in receipt['files']:raise ValueError('unbound new parent')
            for filename,expected in receipt['files'].items():
                raw=payloads[name+':parent:'+filename]
                if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('corrupt new parent')
            if hashlib.sha256(payloads[name]).hexdigest()!=receipt['files']['candidate.csv']:raise ValueError('candidate/parent mismatch')
            frame=pd.read_csv(io.BytesIO(payloads[name]))
            if frame.Date.tolist()!=dates:raise ValueError('candidate date support mismatch')
            candidate={'name':name,'direction':'higher_risk','provenance':'registered captured campaign CSV',
                       'values':[{'date':d,'value':float(v)} for d,v in zip(dates,frame[column])]}
            if name=='attention_surge_risk':
                if not frame.available.isin([True,False]).all():raise ValueError('invalid availability boolean')
                availability={'name':name,'values':frame.available.astype(int).tolist()}
        candidates.append(candidate)
    return snapshot,candidates,availability,json.loads(payloads['atlas'])


def run(registration_path,output):
    raw=bounded(registration_path)
    output=safe_path(Path(output)).resolve();output.mkdir(parents=True,exist_ok=False)
    publish(output/'registration.json',raw)
    try:
        registered=json.loads(raw);payloads=capture(registered)
        result=model.evaluate(*inputs(payloads));result['registration_id']=registered['registration_id']
        write_packet(output,{'study.json':canonical_bytes(result)},bound_existing=('registration.json',))
    except Exception as error:
        if not (output/'receipt.json').exists():write_packet(output,{'error.json':canonical_bytes({'status':'failed_no_retuning','error':str(error)})},bound_existing=('registration.json',))
        raise
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    reg=sub.add_parser('register');reg.add_argument('--root',type=Path,required=True);reg.add_argument('--bundle',type=Path,required=True);reg.add_argument('--atlas',type=Path,required=True);reg.add_argument('--output',type=Path,required=True)
    replay=sub.add_parser('run');replay.add_argument('--registration',type=Path,required=True);replay.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='register':publish(args.output,canonical_bytes(build_registration(args.root,args.bundle,args.atlas)))
    else:run(args.registration,args.output)

if __name__=='__main__':main()
