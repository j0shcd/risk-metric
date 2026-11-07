"""Hash-bound benchmark atlas; measurement against every reference, never promotion.

Build only from verified frozen packets. Issued CDFs are scored without finite-
ensemble corrections; generative replicas retain their registered fair losses.
Extra generative origins are not comparison evidence. Two replicas supply a
numerical stability guard, not a confidence interval or significance test.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
from .market_dataset import TARGETS, COMPONENTS, canonical_bytes, digest
from .market_information import PROTOCOL as DIRECT_PROTOCOL
from .generative_forecast_scorecard import (PROTOCOL as GENERATIVE_PROTOCOL,
    code_identity as scorecard_code, runtime_identity, distribution_summary, sha)
from .scorecard_artifacts import verify_packet, write_packet, safe_path

PROTOCOL = {'id':'benchmark-frontier-v1','horizons':[12,24,48],
            'mc_guard':'both gains positive; replica difference <20% of smaller gain, separately per loss',
            'promotion':'none; completed means valid measurement only'}
IDENTITY = ('source_sha256','dataset_id','snapshot_id','code_sha256','protocol','as_of',
            'development_cutoff','outer_start','minimum_training')
DIRECT_NAMES = (*COMPONENTS, 'price_trend_12m', 'price_volatility_90d', 'price_drawdown_12m',
                'price_ath_drawdown', 'price_log_sma_200d', 'time_years_since_2012',
                'calendar_cycle_sin_4y', 'calendar_cycle_cos_4y')
METRICS = ('crps','brier','coverage_50','coverage_80','width_50','width_80')
MAX_ATLAS_BYTES = 16*1024*1024


def code_identity():
    return {**scorecard_code(),**{name:sha(Path(__file__).with_name(name).read_bytes()) for name in ('benchmark_frontier.py','generative_price_baseline.py')}}


def key(r): return (r['date'],r['horizon'],r['target'])
def outcome(r): return tuple(r.get(k) for k in ('role','outcome','entry','end','label_available'))
def mapping(records):
    result={key(r):r for r in records}
    if len(result)!=len(records): raise ValueError('duplicate forecast origin')
    if any(k[1] not in PROTOCOL['horizons'] or k[2] not in TARGETS for k in result):
        raise ValueError('unsupported horizon/target')
    return result


def issued(record, weights):
    result={k:record[k] for k in ('date','horizon','target','role','outcome','entry','end','label_available')}
    result['status']='scored' if record['outcome'] is not None else 'unscored'
    result.update(distribution_summary(record['atoms'],weights,result['target'],result['outcome']))
    return result


def build_atlas(reference_packet, generative_packet):
    reference_packet,generative_packet=Path(reference_packet),Path(generative_packet)
    receipts={p:verify_packet(p) for p in (reference_packet,generative_packet)}
    def capture(p,name):
        raw=(p/name).read_bytes()
        if sha(raw)!=receipts[p]['files'].get(name): raise ValueError('frozen packet changed during capture')
        return raw
    raw=capture(reference_packet,'replay.json'); replay=json.loads(raw)
    gen=json.loads(capture(generative_packet,'scorecard.json'))
    reg=json.loads(capture(generative_packet,'registration.json'))
    refs=replay['references']
    if not refs: raise ValueError('named direct references required')
    identity={k:refs[0][k] for k in IDENTITY}
    if (identity['protocol']!=DIRECT_PROTOCOL or identity['minimum_training']!=24
            or identity['as_of']>'2022-12-31' or identity['development_cutoff']!='2022-12-31'
            or gen['protocol']!=GENERATIVE_PROTOCOL or gen['registration']!=reg
            or reg['reference_replay_sha256']!=sha(raw)
            or reg['source_sha256']!=identity['source_sha256']
            or gen['source_sha256']!=identity['source_sha256'] or gen['as_of']!=identity['as_of']
            or gen['code_sha256']!=reg['scorecard_code_sha256'] or gen['runtime']!=reg['runtime']
            or gen['reference_identity']!=digest(refs) or reg['protocol']!=GENERATIVE_PROTOCOL
            or gen['code_sha256']!=scorecard_code() or gen['runtime']!=runtime_identity()
            or reg['model_source_sha256']!=sha(Path(__file__).with_name('generative_price_baseline.py').read_bytes())):
        raise ValueError('frozen packet source/protocol/registration mismatch')
    models=[];base=mapping(refs[0]['predictions'])
    for ref in refs:
        if {k:ref[k] for k in IDENTITY}!=identity: raise ValueError('direct reference identity mismatch')
        records=mapping(ref['predictions'])
        if records.keys()!=base.keys() or any(outcome(records[k])!=outcome(base[k]) for k in base):
            raise ValueError('direct reference origins/outcomes mismatch')
        models.append({'name':'direct_cdf:'+ref['candidate_name'],'kind':'issued_cdf','replica':None,
                       'records':[issued(r,r['candidate_weights']) for r in ref['predictions']]})
    for name in ('context','unconditional'):
        models.append({'name':name,'kind':'issued_cdf','replica':None,'records':[
            issued(r,r['reference_weights'] if name=='context' else np.full(len(r['atoms']),1/len(r['atoms']))) for r in base.values()]})
    for replica in (0,1):
        records=[r for r in gen['records'] if r['model']=='generative' and r['replica']==replica]
        mapped=mapping(records)
        if not records or any(k not in mapped or outcome(mapped[k])!=outcome(base[k]) for k in base):
            raise ValueError('generative origins/outcomes mismatch')
        models.append({'name':'generative','kind':'iid_predictive_law_draws','replica':replica,'records':records})
    if mapping(models[-1]['records']).keys()!=mapping(models[-2]['records']).keys():
        raise ValueError('replica support mismatch')
    atlas={'protocol':PROTOCOL,'identity':identity,'code_sha256':code_identity(),'runtime':runtime_identity(),
           'parents':{str(p.name):digest(receipts[p]) for p in (reference_packet,generative_packet)},
           'reference_inventory':[(m['name'],m['replica']) for m in models],
           'generative_registration':reg,'models':models}
    atlas['atlas_id']=digest(atlas)
    if len(canonical_bytes(atlas))>MAX_ATLAS_BYTES: raise ValueError('atlas byte limit exceeded')
    validate_atlas(atlas,identity['source_sha256']);return atlas


def validate_atlas(atlas, source_sha256):
    if (atlas['protocol']!=PROTOCOL or atlas['code_sha256']!=code_identity()
            or atlas['runtime']!=runtime_identity() or atlas['identity']['source_sha256']!=source_sha256
            or atlas['atlas_id']!=digest({k:v for k,v in atlas.items() if k!='atlas_id'})):
        raise ValueError('atlas source/protocol/code/runtime/digest mismatch')
    models=atlas['models'];names=[(m['name'],m['replica']) for m in models]
    if names!=[tuple(n) for n in atlas['reference_inventory']]: raise ValueError('atlas reference inventory mismatch')
    if len(set(names))!=len(names) or ('generative',0) not in names or ('generative',1) not in names or ('unconditional',None) not in names or ('context',None) not in names:
        raise ValueError('atlas reference family incomplete')
    direct=[m for m in models if m['name'].startswith('direct_cdf:')]
    if {m['name'] for m in direct}!={'direct_cdf:'+name for name in DIRECT_NAMES} or len(models)!=len(DIRECT_NAMES)+4:
        raise ValueError('atlas requires every frozen direct reference and both generative replicas')
    base=mapping(direct[0]['records'])
    for model in models:
        records=mapping(model['records'])
        if (model['kind']=='issued_cdf' and records.keys()!=base.keys()) or any(k not in records or outcome(records[k])!=outcome(base[k]) for k in base):
            raise ValueError('atlas reference origins/outcomes mismatch')
    return atlas


def read_atlas(path, source_sha256):
    with Path(path).open('rb') as f: raw=f.read(MAX_ATLAS_BYTES+1)
    if len(raw)>MAX_ATLAS_BYTES: raise ValueError('atlas byte limit exceeded')
    atlas=json.loads(raw);validate_atlas(atlas,source_sha256);return atlas


def compare_trial(atlas, trial):
    result=trial['result'];validate_atlas(atlas,result['source_sha256'])
    if {k:result[k] for k in IDENTITY}!=atlas['identity']:
        raise ValueError('trial source/outcome/protocol identity mismatch')
    predicted=mapping(result['predictions']);base=mapping(atlas['models'][0]['records'])
    if predicted.keys()!=base.keys() or any(outcome(predicted[k])!=outcome(base[k]) for k in base):
        raise ValueError('trial origins/outcomes mismatch')
    candidate={k:issued(r,r['candidate_weights']) for k,r in predicted.items()}
    cells=[]
    for model in atlas['models']:
        reference=mapping(model['records'])
        for role in ('development','outer','retrospective_challenge','pending','outcome_unavailable'):
            for horizon in PROTOCOL['horizons']:
                for target in TARGETS:
                    keys=[k for k,r in base.items() if (r['role'],k[1],k[2])==(role,horizon,target)]
                    scored=[k for k in keys if candidate[k]['status']=='scored' and reference[k]['status']=='scored']
                    failed=[k for k in keys if reference[k]['status']=='numerical_failure']
                    expected=[k for k in keys if candidate[k]['status']=='scored']
                    complete=len(scored)==len(expected) and not failed
                    values={metric:None for metric in METRICS};candidate_means=dict(values);reference_means=dict(values)
                    if complete and scored:
                        for metric in METRICS:
                            candidate_means[metric]=float(np.mean([candidate[k][metric] for k in scored]))
                            reference_means[metric]=float(np.mean([reference[k][metric] for k in scored]))
                            values[metric]=float(np.mean([reference[k][metric]-candidate[k][metric] for k in scored]))
                    cells.append({'reference':model['name'],'replica':model['replica'],'role':role,'horizon':horizon,'target':target,
                                  'requested_n':len(keys),'scored_n':len(scored),'failure_n':len(failed),'unavailable_n':len(keys)-len(scored)-len(failed),
                                  'extra_reference_origins_excluded_n':sum((r['role'],k[1],k[2])==(role,horizon,target) and k not in base for k,r in reference.items()),
                                  'scored_origins_id':digest(sorted(k[0] for k in scored)),
                                  'candidate':candidate_means,'reference_means':reference_means,'reference_minus_candidate':values})
    guards=[]
    for a in (c for c in cells if c['reference']=='generative' and c['replica']==0):
        b=next(c for c in cells if c['reference']=='generative' and c['replica']==1 and all(c[k]==a[k] for k in ('role','horizon','target')))
        for metric in ('crps','brier'):
            gains=[c['reference_minus_candidate'][metric] for c in (a,b)]
            passes=all(g is not None and g>0 for g in gains) and abs(gains[0]-gains[1])<.2*min(gains)
            guards.append({k:a[k] for k in ('role','horizon','target')}|{'metric':metric,'replica_gains':gains,'numerically_stable_gain':bool(passes)})
    return {'atlas_id':atlas['atlas_id'],'candidate_id':result['candidate_id'],'status':'completed_measurement_not_promotion',
            'cells':cells,'mc_guards':guards,'ordering_diagnostics':[{k:c[k] for k in ('role','horizon','target','ordinal_alignment','diagnostic_n','diagnostic_origins_id')} for c in result['cells']],
            'limitations':['Ordering is separate from forecast loss. No scalar winner or automatic promotion.',
                           'Coverage/width and Brier tradeoffs remain separate. Positive loss delta means lower candidate loss.',
                           'Extra generative origins excluded; unavailable/failure cells retained; MC guard is not significance.']}


def readable(comparison):
    lines=['# Benchmark frontier comparison','','Completed measurement; no automatic promotion. Positive loss delta favors candidate; coverage/width are separate tradeoffs.','',
           '| Role | Months | Target | Reference | Replica | Scored / failed / unavailable | CRPS delta | Brier delta | 50% coverage delta / width delta | 80% coverage delta / width delta |','|---|---:|---|---|---:|---|---:|---:|---|---|']
    for c in comparison['cells']:
        def show(v):return '—' if v is None else f'{v:.6f}'
        lines.append(f"| {c['role']} | {c['horizon']} | {c['target']} | {c['reference']} | {c['replica']} | {c['scored_n']} / {c['failure_n']} / {c['unavailable_n']} | {show(c['reference_minus_candidate']['crps'])} | {show(c['reference_minus_candidate']['brier'])} | {show(c['reference_minus_candidate']['coverage_50'])} / {show(c['reference_minus_candidate']['width_50'])} | {show(c['reference_minus_candidate']['coverage_80'])} / {show(c['reference_minus_candidate']['width_80'])} |")
    lines+=['','MC guard (numerical only, not significance):',*['- '+str(g) for g in comparison['mc_guards']],
            '', 'Fixed-direction ordering, separate from forecast quality:',*['- '+str(c) for c in comparison['ordering_diagnostics']]]
    return ('\n'.join(lines)+'\n').encode()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-packet',type=Path,required=True);parser.add_argument('--generative-packet',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True);args=parser.parse_args(argv)
    atlas=build_atlas(args.reference_packet,args.generative_packet);target=safe_path(args.output_dir);target.mkdir(exist_ok=False)
    write_packet(target,{'atlas.json':canonical_bytes(atlas)})
    print(json.dumps({'atlas_id':atlas['atlas_id'],'output':str(target)}))

if __name__=='__main__':main()
