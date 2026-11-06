"""Frozen development-only decoder ablation; no selection or outer replay."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .distribution_readout import weighted_crps
from .market_dataset import TARGETS, build_dataset, canonical_bytes, digest, load_snapshot
from .market_information import baseline_candidates
from .market_scorecard import validate_candidate
from .scorecard_artifacts import publish, safe_path, write_packet

CUTOFF = '2022-12-31'
PROTOCOL = {'cutoff': CUTOFF, 'horizons': [12, 24], 'primary': '24-month terminal_log_return',
            'training_n': 24, 'neighbors': 8, 'pooled_mass': .5,
            'arms': ['indicator_median', 'combined_median', 'indicator_rank', 'combined_rank'],
            'rank': '(count less + .5 count equal)/training_n; query ranked against training only',
            'distance': 'mean absolute rank distance; fractional boundary ties atol=1e-12',
            'events': 'return<0; entry loss>log(2); peak drawdown>log(2)',
            'coverage': 'inclusive central 50% and 80%; left inverse weighted empirical CDF',
            'fallback': 'empty combined median -> context median; empty indicator median -> uniform'}

def percentile(train, query):
    """Common training-only mid-CDF transform, including out-of-range queries."""
    train, query = np.asarray(train, float), np.asarray(query, float)
    n = len(train)
    ranked = ((train[:, None, :] < train[None, :, :]).sum(axis=0)
              + .5 * (train[:, None, :] == train[None, :, :]).sum(axis=0)) / n
    q = ((train < query).sum(axis=0) + .5 * (train == query).sum(axis=0)) / n
    return ranked, q

def decode(train, query, method, fallback=None):
    train, query = np.asarray(train, float), np.asarray(query, float)
    if (train.ndim != 2 or len(train) != 24 or train.shape[1] < 1 or query.shape != (train.shape[1],)
            or not np.isfinite(train).all() or not np.isfinite(query).all()):
        raise ValueError('Require 24 finite training rows and a finite matching query')
    uniform = np.full(len(train), 1 / len(train))
    empty = False
    if method == 'median':
        cuts = np.median(train, axis=0)
        membership = np.all((train > cuts) == (query > cuts), axis=1).astype(float)
        empty = not membership.any()
        if empty:
            weights = uniform if fallback is None else np.asarray(fallback, float).copy()
        else:
            weights = .5 * uniform + .5 * membership / membership.sum()
    elif method == 'rank':
        ranks, q = percentile(train, query)
        distance = np.abs(ranks-q).mean(axis=1)
        boundary = np.sort(distance)[7]
        ties = np.isclose(distance, boundary, rtol=0, atol=1e-12)
        inside = (distance < boundary) & ~ties
        membership = inside.astype(float) + ties * ((8-int(inside.sum())) / int(ties.sum()))
        weights = .5 * uniform + .5 * membership / 8
    else:
        raise ValueError('Unknown decoder')
    return weights, {'fallback': empty, 'local_mass': float(membership.sum()),
                     'local_nonzero_n': int((membership > 0).sum()),
                     'weight_concentration_n': float(1 / np.square(weights).sum())}

def event_mask(atoms, target):
    if target == 'terminal_log_return':
        return np.asarray(atoms) < 0
    if target in ('entry_adverse_log_loss', 'peak_drawdown_log_loss'):
        return np.asarray(atoms) > np.log(2.)
    raise ValueError('Unknown target')

def diagnostics(atoms, weights, observed, target):
    order = np.argsort(atoms)
    x, w = np.asarray(atoms)[order], np.asarray(weights)[order]
    def quantile(q):
        return float(x[min(np.searchsorted(np.cumsum(w), q), len(x)-1)])
    out = {'crps': weighted_crps(atoms, weights, observed),
           'outside_atom_range': bool(observed < x[0] or observed > x[-1])}
    for level, tail in [(50, .25), (80, .1)]:
        lo, hi = quantile(tail), quantile(1-tail)
        out.update({f'coverage_{level}': bool(lo <= observed <= hi), f'width_{level}': hi-lo})
    p = float(np.dot(weights, event_mask(atoms, target)))
    y = bool(event_mask([observed], target)[0])
    out.update({'event_probability': p, 'event_occurred': y, 'brier': (p-float(y))**2})
    return out

def evaluate(snapshot, candidates):
    if snapshot['daily'][-1]['date'] > CUTOFF:
        raise ValueError('No post-development data permitted')
    dataset = build_dataset(snapshot, [12,24])
    rows = dataset['rows']
    values = {c['name']: validate_candidate(c, rows) for c in candidates}
    if len(values) != len(candidates):
        raise ValueError('Duplicate candidate name')
    records = []
    support = {}
    for horizon in [12,24]:
        key = str(horizon)
        eligible = lambda r: r['context'] is not None and np.isfinite(r['context']).all()
        support[key] = []
        for i, row in enumerate(rows):
            outcome = row['outcomes'][key]
            if not eligible(row) or outcome['status'] != 'complete' or outcome['available'] > CUTOFF:
                continue
            train = [j for j in range(i) if eligible(rows[j]) and rows[j]['outcomes'][key]['status']=='complete'
                     and rows[j]['outcomes'][key]['available'] < row['date']][-24:]
            if len(train) != 24:
                continue
            support[key].append(row['date'])
            context = np.array([rows[j]['context'] for j in train])
            query = np.array(row['context'])
            contextual = {method: decode(context, query, method) for method in ['median','rank']}
            forecasts = [('unconditional','unconditional',np.full(24,1/24),{'fallback':False,'local_mass':24.,'local_nonzero_n':24,'weight_concentration_n':24.},None,None)]
            for method,(weights,info) in contextual.items():
                forecasts.append(('context',method,weights,info,None,None))
            for candidate in candidates:
                name = candidate['name']
                feature, current = values[name][train,None], values[name][i]
                for method in ['median','rank']:
                    w,info = decode(feature, np.array([current]), method)
                    forecasts.append((name,'indicator_'+method,w,info,float(current),candidate['direction']))
                    w,info = decode(np.column_stack([context,feature]),np.r_[query,current],method,contextual[method][0])
                    forecasts.append((name,'combined_'+method,w,info,float(current),candidate['direction']))
            for target_index,target in enumerate(TARGETS):
                atoms = np.array([rows[j]['outcomes'][key]['values'][target_index] for j in train])
                observed = outcome['values'][target_index]
                for name,arm,weights,info,score,direction in forecasts:
                    records.append({'candidate':name,'arm':arm,'horizon':horizon,'target':target,'date':row['date'],
                                    'train_dates':[rows[j]['date'] for j in train],
                                    'last_train_label_available':max(rows[j]['outcomes'][key]['available'] for j in train),
                                    'outcome':observed,'score':score,'direction':direction,
                                    'atoms':atoms.tolist(),'weights':weights.tolist(),**info,
                                    **diagnostics(atoms,weights,observed,target)})
    groups = {}
    for record in records:
        key=(record['candidate'],record['arm'],record['horizon'],record['target'])
        groups.setdefault(key,[]).append(record)
    cells=[]
    for (name,arm,horizon,target), group in groups.items():
        cell={'candidate':name,'arm':arm,'horizon':horizon,'target':target,'n':len(group),
              'origins_id':digest([r['date'] for r in group])}
        for field in ['crps','coverage_50','coverage_80','width_50','width_80','outside_atom_range','brier','weight_concentration_n','local_mass','local_nonzero_n','fallback']:
            cell[field]=float(np.mean([r[field] for r in group]))
        correlation=None
        if group[0]['score'] is not None:
            a=pd.Series([r['score'] for r in group]).rank().to_numpy()
            b=pd.Series([r['outcome'] for r in group]).rank().to_numpy()
            if np.ptp(a)>0 and np.ptp(b)>0: correlation=float(np.corrcoef(a,b)[0,1])
        cell['spearman_same_origins']=correlation
        cell['declared_alignment']=None if correlation is None or group[0]['direction']!='higher_risk' else correlation*(-1 if target=='terminal_log_return' else 1)
        # Fixed coarse reliability bins, diagnostic only; no fitted recalibration.
        cell['reliability']=[]
        for lo,hi in [(0,.25),(.25,.5),(.5,.75),(.75,1.0000001)]:
            members=[r for r in group if lo<=r['event_probability']<hi]
            cell['reliability'].append({'lower':lo,'upper':min(hi,1.),'n':len(members),
                 'mean_probability':float(np.mean([r['event_probability'] for r in members])) if members else None,
                 'observed_frequency':float(np.mean([r['event_occurred'] for r in members])) if members else None})
        cells.append(cell)
    for c in cells:
        assert c['origins_id']==digest(support[str(c['horizon'])])
    return {'protocol':PROTOCOL,'dataset_id':digest(dataset),'support':support,'cells':cells,'predictions':records,
            'limitations':['Overlapping outcomes, not independent samples; no calibration/significance claim.',
                           'Historical source vintages and daily UTC close convention unverified.',
                           'Only development outcomes through2022; no outer access; no scalar winner.']}

def run(bundle, output):
    manifest=json.loads((bundle/'manifest.json').read_text())
    if manifest['cutoff']!=CUTOFF: raise ValueError('Wrong development cutoff')
    for name in ['development_scores.csv','btc_daily.csv']:
        if hashlib.sha256((bundle/name).read_bytes()).hexdigest()!=manifest['sources'][name]['development_sha256']:
            raise ValueError('Input hash mismatch')
    snapshot=load_snapshot(bundle/'development_scores.csv')
    raw=pd.read_csv(bundle/'btc_daily.csv')
    if pd.to_datetime(raw.Date).max()>pd.Timestamp(CUTOFF): raise ValueError('Future prices prohibited')
    from .candidates.swing_b.generator import generate
    fixed=generate(raw)['swing_b_adaptive']
    candidates=baseline_candidates(snapshot)
    candidates.append({'name':'swing_b_adaptive','direction':'higher_risk','provenance':'frozen8837516',
                       'values':[{'date':r['date'],'value':float(fixed.loc[r['date']])} for r in snapshot['monthly']]})
    result=evaluate(snapshot,candidates)
    result['source_hashes']={name:hashlib.sha256((bundle/name).read_bytes()).hexdigest() for name in ['manifest.json','development_scores.csv','btc_daily.csv']}
    result['code_hashes']={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ['readout_study.py','market_dataset.py','market_information.py','market_scorecard.py','distribution_readout.py']}
    result['generator_sha256']=hashlib.sha256(Path(__file__).parent.joinpath('candidates/swing_b/generator.py').read_bytes()).hexdigest()
    write_packet(output,{'study.json':canonical_bytes(result)},bound_existing=('request.json',))
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args()
    output=safe_path(args.output_dir); output.mkdir(exist_ok=False)
    publish(output/'request.json',canonical_bytes({'bundle':str(args.bundle),'protocol':PROTOCOL}))
    try: result=run(args.bundle,output)
    except Exception as error:
        publish(output/'error.json',canonical_bytes({'error':str(error)})); raise
    print(json.dumps({'output':str(output),'cells':len(result['cells']),'support':{k:len(v) for k,v in result['support'].items()}}))

if __name__=='__main__': main()
