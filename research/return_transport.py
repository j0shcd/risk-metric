"""Last bounded retrospective return-decoder diagnostic; never calibrated or promoted.

Feature-only preprocessing is frozen across leave-one-LABEL-out refits. Query
features affect exact equivalence classes only, never rank cuts/centering/scales.
PRESS is therefore a fixed-design diagnostic, not full preprocessing crossfit.
"""
from __future__ import annotations
import hashlib
import platform
from pathlib import Path
import numpy as np
import pandas as pd
from .market_dataset import build_dataset, canonical_bytes, digest
from .market_information import baseline_candidates
from .market_scorecard import validate_candidate
from .readout_study import diagnostics
from .benchmark_frontier import validate_atlas, mapping, outcome, METRICS

PROTOCOL = {'id':'return-transport-v1','training_n':24,'ridge_lambda':24,
 'horizons':[12,24],'primary':'24-month terminal_log_return','cutoff':'2022-12-31',
 'preprocessing':'training midpercentiles, ddof0 standardization; fixed all24 feature design in LOO',
 'equivalence':'exact integer midrank coordinates including query; complements identified; constants dropped',
 'residuals':'fixed-design PRESS; fixed lambda24 in each23-label refit; uniform24 atoms',
 'support':'same48/24 development origins as frozen atlas; no support selection',
 'attention':'context+mask and context+mask+attention, plus ordinary context+attention',
 'interpretation':'issued CDF, no fair ensemble correction; no calibration/significance/promotion',
 'slope_direction':'unconstrained; forecast information is not fixed higher-risk ordering',
 'stopping_rule':'one frozen study; no further lambda/decoder search if unsuccessful',
 'intercept_control':'mean+(24/23)*(y-mean), distinct from uniform raw outcome CDF'}


def design(train, query):
    train, query = np.asarray(train,float), np.asarray(query,float)
    if train.ndim != 2 or train.shape[0] != 24 or query.shape != (train.shape[1],) or not np.isfinite(train).all() or not np.isfinite(query).all():
        raise ValueError('require24 finite feature rows and matching query')
    # Integers avoid floating equivalence ambiguities, including complements.
    rank = 2*(train[:,None,:] < train[None,:,:]).sum(axis=0)+(train[:,None,:] == train[None,:,:]).sum(axis=0)
    qr = 2*(train < query).sum(axis=0)+(train == query).sum(axis=0)
    classes = set()
    for j in range(train.shape[1]):
        if np.ptp(rank[:,j]) == 0: continue
        coordinate = tuple(int(v) for v in np.r_[rank[:,j],qr[j]])
        complement = tuple(48-v for v in coordinate)
        classes.add(min(coordinate,complement))
    coordinates = np.array(sorted(classes),float).reshape(-1,25).T
    x, q = coordinates[:24]/48, coordinates[24]/48
    if x.shape[1]:
        center, scale = x.mean(axis=0), x.std(axis=0,ddof=0)
        x, q = (x-center)/scale, (q-center)/scale
    return np.column_stack([np.ones(24),x]), np.r_[1.,q]


def transport(train, query, labels):
    y=np.asarray(labels,float)
    if y.shape!=(24,) or not np.isfinite(y).all():raise ValueError('require24 finite labels')
    x,q=design(train,query)
    penalty=np.diag([0.]+[24.]*(x.shape[1]-1))
    inverse=np.linalg.solve(x.T@x+penalty,x.T)
    coefficients=inverse@y
    leverage=np.sum(x*inverse.T,axis=1)
    if np.any(1-leverage<=1e-10):raise ValueError('unstable PRESS leverage')
    residuals=(y-x@coefficients)/(1-leverage)
    location=float(q@coefficients);atoms=location+residuals
    if not np.isfinite(atoms).all():raise ValueError('nonfinite transported atoms')
    return {'atoms':atoms.tolist(),'location':location,'loo_residuals':residuals.tolist(),
            'leverage':leverage.tolist(),'coordinate_n':x.shape[1]-1}


def evaluate(snapshot,candidates,availability,atlas):
    """In-memory owning boundary; caller must capture/hash/register inputs first."""
    if snapshot['daily'][-1]['date']>PROTOCOL['cutoff']:raise ValueError('postdevelopment source forbidden')
    validate_atlas(atlas,snapshot['source_sha256'])
    rows=build_dataset(snapshot,[12,24])['rows']
    if len(candidates)!=6 or len({c['name'] for c in candidates})!=6:raise ValueError('require six frozen arms')
    refs=baseline_candidates(snapshot)
    if len(refs)!=13:raise ValueError('require13 fixed references')
    names=[c['name'] for c in refs+candidates]
    if len(set(names))!=19:raise ValueError('duplicate model name')
    values={c['name']:validate_candidate(c,rows) for c in refs+candidates}
    mask=np.asarray(availability['values'],float)
    if mask.shape!=(len(rows),) or not np.isin(mask,[0,1]).all() or availability['name'] not in values:raise ValueError('invalid attention mask')
    context=np.asarray([r['context'] for r in rows],float)
    if context.shape!=(len(rows),2) or not np.isfinite(context).all():raise ValueError('common finite context required')
    models={'intercept':np.empty((len(rows),0)),'context':context}
    models.update({'context+'+name:np.column_stack([context,v]) for name,v in values.items()})
    models['context+availability']=np.column_stack([context,mask])
    models['context+availability+attention']=np.column_stack([context,mask,values[availability['name']]])
    base=mapping(atlas['models'][0]['records']);records=[]
    for h in (12,24):
        expected={k for k,r in base.items() if k[1:]==(h,'terminal_log_return') and r['role']=='development' and r['status']=='scored'}
        actual=set()
        for i,row in enumerate(rows):
            target=row['outcomes'][str(h)]
            if target['status']!='complete' or target['available']>PROTOCOL['cutoff']:continue
            mature=[j for j in range(i) if rows[j]['outcomes'][str(h)]['status']=='complete' and rows[j]['outcomes'][str(h)]['available']<row['date']][-24:]
            if len(mature)!=24:continue
            key=(row['date'],h,'terminal_log_return');actual.add(key)
            common={'date':row['date'],'horizon':h,'target':'terminal_log_return','role':'development',
                    'outcome':target['values'][0],'entry':target['entry'],'end':target['end'],'label_available':target['available']}
            if key not in expected or outcome(common)!=outcome(base[key]):raise ValueError('atlas outcome/support mismatch')
            labels=np.array([rows[j]['outcomes'][str(h)]['values'][0] for j in mature])
            for name,features in models.items():
                prediction=transport(features[mature],features[i],labels)
                records.append({**common,'model':name,'status':'scored',**prediction,
                   **diagnostics(np.array(prediction['atoms']),np.full(24,1/24),target['values'][0],'terminal_log_return'),
                   'train_dates':[rows[j]['date'] for j in mature], 'train_available_n':int(mask[mature].sum()),
                   'query_available':bool(mask[i])})
        if actual!=expected or len(actual)!={12:48,24:24}[h]:raise ValueError('frozen common support changed')
    cells=[]
    for name in models:
        for h in (12,24):
            selected=[r for r in records if r['model']==name and r['horizon']==h]
            for reference in atlas['models']:
                ref=mapping(reference['records']);paired=[ref[(r['date'],h,r['target'])] for r in selected]
                failures=sum(r['status']!='scored' for r in paired)
                cell={'model':name,'horizon':h,'reference':reference['name'],'replica':reference['replica'],
                      'n':len(selected),'failure_n':failures,'means':{},'reference_minus_model':{}}
                for metric in METRICS:
                    cell['means'][metric]=float(np.mean([r[metric] for r in selected]))
                    cell['reference_minus_model'][metric]=None if failures else float(np.mean([p[metric]-r[metric] for p,r in zip(paired,selected)]))
                cells.append(cell)
    contributions=[]
    for name in models:
        for h in (12,24):
            for available in (False,True):
                subset=[r for r in records if r['model']==name and r['horizon']==h and r['query_available']==available]
                contributions.append({'model':name,'horizon':h,'query_available':available,'n':len(subset),
                     'crps_sum':float(sum(r['crps'] for r in subset)),'crps_mean':float(np.mean([r['crps'] for r in subset])) if subset else None})
    matched=[]
    for name in models:
        comparator='context+availability' if name=='context+availability+attention' else 'context'
        for h in (12,24):
            selected=[r for r in records if r['model']==name and r['horizon']==h]
            reference=[r for r in records if r['model']==comparator and r['horizon']==h]
            matched.append({'model':name,'reference':comparator,'horizon':h,'n':len(selected),
                'reference_minus_model':{metric:float(np.mean([p[metric]-r[metric] for p,r in zip(reference,selected)])) for metric in METRICS}})
    guards=[]
    for cell in (c for c in cells if c['reference']=='generative' and c['replica']==0):
        other=next(c for c in cells if c['model']==cell['model'] and c['horizon']==cell['horizon'] and c['reference']=='generative' and c['replica']==1)
        for metric in ('crps','brier'):
            gains=[c['reference_minus_model'][metric] for c in (cell,other)]
            passes=all(g is not None and g>0 for g in gains) and abs(gains[0]-gains[1])<.2*min(gains)
            guards.append({'model':cell['model'],'horizon':cell['horizon'],'metric':metric,'gains':gains,'numerically_stable_gain_not_significance':bool(passes)})
    return {'protocol':PROTOCOL,'records':records,'cells':cells,'availability_contributions':contributions,
            'matched_decoder_contrasts':matched,'mc_guards':guards,
            'atlas_id':atlas['atlas_id'],'status':'measurement_only_no_selection'}


def registration(inputs):
    """Bind a declarative inventory of files; root freezes it before any execution.

    Inputs is a mapping role -> path. Include bundle manifest/development CSV,
    old trial ZIPs, all new campaign CSVs, producer configs, atlas and inventory.
    This builder hashes bytes only and never parses or fits market observations.
    """
    files={name:{'path':str(Path(path).resolve()),'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()} for name,path in inputs.items()}
    code={str(p.relative_to(Path(__file__).parents[1])):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.rglob('*.py'))}
    result={'protocol':PROTOCOL,'inputs':files,'code':code,'runtime':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__}}
    result['registration_id']=digest(result)
    return result
