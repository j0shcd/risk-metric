"""Frozen monthly-observation portability falsification, separate from BTC daily.

No provider observations are bundled or read at import/registration. Register
before the first provider run and obtain root source-review approval. Only the
three frozen price generators and eight declared monthly references are used.
Outputs contain derived provider values and must remain under the ignored local
PRIVATE_ROOT; redistribution is not cleared. No daily interpolation or policy.

CLI: python -m research.monthly_portability register --registration PATH
     python -m research.monthly_portability run --registration PATH
         --source PRIVATE_MONTHLY_CSV --output-dir NEW_PRIVATE_DIRECTORY
Registration/data/code/runtime mismatches fail closed. A new output directory is
not a new holdout; the root owns the single approved external test and integration.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
import platform
import numpy as np
import pandas as pd
from .candidates.swing_a.indicator import generate_indicator
from .candidates.swing_b.generator import generate as generate_b
from .candidates.swing_c.generate import generate as generate_c
from .distribution_readout import mixture_forecasts
from .readout_study import diagnostics, event_mask
from .market_dataset import canonical_bytes, digest, TARGETS
from .scorecard_artifacts import publish, safe_path, write_packet

ROOT=Path(__file__).resolve().parents[1]
PRIVATE_ROOT=ROOT/'data/external_private'
FIXTURE_METADATA=Path('research/fixtures/french_monthly_2026-11-07.json')
ERAS={'older_family_falsification':('1990-01-31','2003-12-31'),
      'shared_era_challenge':('2004-01-31','2017-12-31')}
CANDIDATES=('swing_a_memory_0','swing_b_adaptive','swing_c_24m')
REFERENCES=('monthly_trend_12m','monthly_volatility_12m','monthly_drawdown_12m',
            'monthly_ath_drawdown','monthly_log_sma_12m','elapsed_months_1970',
            'calendar_sin_48m','calendar_cos_48m')
PROTOCOL={
 'id':'french-monthly-portability-v1','asset':'french_broad_us_research_market_total_return',
 'frequency':'monthly_observation','outcome_sampling':'month_end_only',
 'source_cutoff':'2022-12-31','initialization':'1970-01-31 index rebased100',
 'training_origin_start':'1980-01-31','eras':ERAS,'horizons_months':[12,24,48],
 'primary':'24-month terminal_log_return; all other coordinates separate',
 'entry':'next calendar month-end','exit':'entry month plus H calendar months, month-end',
 'label_availability':'exit plus one calendar day; strictly before query for training',
 'targets':list(TARGETS),'training_atoms':24,
 'context':['log(I_t/I_t-12)','std(last12monthly log returns,ddof=1), not annualized'],
 'readout':'existing direct CDF; training-only medians, > ties,50:50 pooled/local; exact context fallback',
 'reference_formulas':{
  'monthly_trend_12m':'log(I_t/I_t-12)',
  'monthly_volatility_12m':'std(last12monthly log returns,ddof=1)',
  'monthly_drawdown_12m':'log(I_t)-max(log(I_t-12..I_t)); current distance below trailing peak',
  'monthly_ath_drawdown':'log(I_t)-max(log(I_1970-01..I_t))',
  'monthly_log_sma_12m':'log(I_t/mean(I_t-11..I_t))',
  'elapsed_months_1970':'integer months since1970-01',
  'calendar_sin_48m':'sin(2*pi*elapsed_months/48)',
  'calendar_cos_48m':'cos(2*pi*elapsed_months/48)'},
 'candidate_parameters':{
  'swing_a_memory_0':{'memory_weight':0.,'anchor_halflife_days':365.,'memory_halflife_days':180.,'observation_lag_days':1,'log_displacement_scale':1.,'initial_memory':0.},
  'swing_b_adaptive':{'alpha':.08,'beta':.004,'damping':.98,'initial_slope':0.,'initial_scale':.25,'scale_ew_alpha':1/24,'scale_floor':.05,'correction_scales':4.,'score_scales':4.},
  'swing_c_24m':{'window':24,'minimum_returns':2,'neutral':50.}},
 'candidate_direction':'higher_risk, no sign changes; A uses previous monthly observation due unchanged1daylag',
 'events':'return<0; both log losses>log(2)',
 'class_counts':'event/non-event, negative/nonnegative return, latest24training pool counts; no one-class discrimination claim',
 'non_overlap':'greedy earliest end within class; next entry strictly after previous exit; not independence',
 'rejection':'negative24m return alignment in both eras OR same fixed comparator no worse in all3 24m outcomes in both eras and strict somewhere; descriptive only',
 'limits':['not daily risk or executable policy','revised vintages/publication availability unverified',
           'shared-era equity outcomes overlap exposed BTC macro shocks','no pre1990freeze or unseenholdout claim',
           'one equity family; do not pool candidates/horizons as independent BTC cycles',
           'single-class event samples cannot establish discrimination; zero-loss skill undefined']}
CODE_FILES=('research/monthly_portability.py','research/distribution_readout.py','research/readout_study.py',
 'research/market_dataset.py','research/market_information.py','research/market_scorecard.py','research/scorecard_artifacts.py',
 'research/candidates/swing_a/indicator.py','research/candidates/swing_b/generator.py','research/candidates/swing_c/generate.py')


def sha(payload):return hashlib.sha256(payload).hexdigest()
def registration():
    metadata=(ROOT/FIXTURE_METADATA).read_bytes();fixture=json.loads(metadata)['fixture']
    record={'status':'registered_before_provider_scoring','protocol':PROTOCOL,
            'fixture_metadata_sha256':sha(metadata),'source_sha256':fixture['sha256'],
            'source_rows':fixture['rows'],'source_first_month':fixture['first_month'],'source_last_month':fixture['last_month'],
            'code_sha256':{name:sha((ROOT/name).read_bytes()) for name in CODE_FILES},
            'runtime':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__}}
    record['registration_id']=digest(record)
    return json.loads(canonical_bytes(record))


def validate_prices(prices):
    prices=prices.copy()
    if (not isinstance(prices.index,pd.DatetimeIndex) or prices.index.tz is not None or prices.index.has_duplicates
        or not prices.index.is_monotonic_increasing or prices.empty or len(prices)>1200
        or not prices.index.equals(prices.index.normalize())
        or not prices.index.equals(pd.date_range(prices.index[0],prices.index[-1],freq='ME'))):
        raise ValueError('require unique consecutive normalized calendar month-ends')
    values=prices.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values<=0).any():raise ValueError('index must be positive and finite')
    if prices.index[-1]>pd.Timestamp(PROTOCOL['source_cutoff']):raise ValueError('post2022observations prohibited')
    if pd.Timestamp('1970-01-31') not in prices.index:raise ValueError('missing fixed1970initialization')
    prices=prices.loc['1970-01-31':].astype(float)
    return prices/prices.iloc[0]*100.


def build_dataset(prices):
    prices=validate_prices(prices);dates=prices.index;logs=np.log(prices);returns=logs.diff()
    trend=logs.diff(12);volatility=returns.rolling(12,min_periods=12).std(ddof=1)
    frame=pd.DataFrame({'Date':dates,'Price':prices.to_numpy()})
    features=pd.DataFrame(index=dates)
    features[CANDIDATES[0]]=generate_indicator(frame,dates=dates,memory_weight=0.,anchor_halflife_days=365.,memory_halflife_days=180.)
    features[CANDIDATES[1]]=generate_b(frame)['swing_b_adaptive']
    features[CANDIDATES[2]]=generate_c(prices,window=24)
    elapsed=np.arange(len(dates),dtype=float)
    for name,values in zip(REFERENCES,(trend,volatility,logs-logs.rolling(13,min_periods=13).max(),
                                      logs-logs.cummax(),np.log(prices/prices.rolling(12,min_periods=12).mean()),
                                      elapsed,np.sin(2*np.pi*elapsed/48),np.cos(2*np.pi*elapsed/48))):
        features[name]=values
    rows=[]
    for i,date in enumerate(dates):
        if date<pd.Timestamp(PROTOCOL['training_origin_start']):continue
        if not np.isfinite(features.iloc[i].to_numpy()).all():raise ValueError('nonfinite common feature support')
        outcomes={}
        for horizon in PROTOCOL['horizons_months']:
            entry_period=date.to_period('M')+1;end_period=entry_period+horizon
            entry=entry_period.to_timestamp('M');end=end_period.to_timestamp('M')
            available=end+pd.Timedelta(days=1)
            values=None
            if i+1+horizon<len(dates):
                path=logs.iloc[i+1:i+2+horizon].to_numpy();relative=path-path[0]
                values=[float(relative[-1]),float(-relative.min()),float(np.max(np.maximum.accumulate(relative)-relative))]
            outcomes[str(horizon)]={'entry':entry.date().isoformat(),'end':end.date().isoformat(),
                                    'available':available.date().isoformat(),'values':values}
        rows.append({'date':date.date().isoformat(),'context':[float(trend.iloc[i]),float(volatility.iloc[i])],
                     'features':{name:float(features.iloc[i][name]) for name in features},'outcomes':outcomes})
    return {'asset':PROTOCOL['asset'],'frequency':PROTOCOL['frequency'],'protocol_id':PROTOCOL['id'],'rows':rows}


def mature_pool(rows,index,horizon):
    key=str(horizon);date=rows[index]['date']
    return [j for j in range(index) if rows[j]['outcomes'][key]['values'] is not None
            and rows[j]['outcomes'][key]['available']<date][-24:]


def forecast_origin(dataset,index,horizon):
    rows=dataset['rows'];row=rows[index];pool=mature_pool(rows,index,horizon)
    if len(pool)!=24:raise ValueError('insufficient24strictlymatureatoms')
    context=np.array([rows[j]['context'] for j in pool]);query=np.array(row['context'])
    base=mixture_forecasts(context,context,query)
    weights={'unconditional':np.full(24,1/24),'context_only':base['reference']}
    info={name:{'fallback':False,'cell_n':24 if name=='unconditional' else base['context_cell_n']} for name in weights}
    info['context_only']['fallback']=base['context_fallback']
    for name in (*CANDIDATES,*REFERENCES):
        training=np.column_stack([context,[rows[j]['features'][name] for j in pool]])
        decoded=mixture_forecasts(training,training,np.r_[query,row['features'][name]])
        weights[name]=decoded['candidate'];info[name]={'fallback':decoded['candidate_fallback'],'cell_n':decoded['candidate_cell_n']}
    return {'date':row['date'],'train_dates':[rows[j]['date'] for j in pool],
            'last_training_label_available':max(rows[j]['outcomes'][str(horizon)]['available'] for j in pool),
            'atoms':np.array([rows[j]['outcomes'][str(horizon)]['values'] for j in pool]),'weights':weights,'info':info}


def nonoverlap_count(records):
    last=None;count=0
    for record in sorted(records,key=lambda r:(r['end'],r['entry'])):
        if last is None or record['entry']>last:count+=1;last=record['end']
    return count


def class_support(records):
    event=[r for r in records if r['event_occurred']];non_event=[r for r in records if not r['event_occurred']]
    counts=[r['training_event_n'] for r in records]
    return {'n':len(records),'event_n':len(event),'non_event_n':len(non_event),
            'event_prevalence':len(event)/len(records) if records else None,
            'nonoverlap_event_n':nonoverlap_count(event),'nonoverlap_non_event_n':nonoverlap_count(non_event),
            'nonoverlap_total_n':nonoverlap_count(records),
            'training_event_counts':counts,'training_non_event_counts':[24-n for n in counts],
            'one_class_training_pools':sum(n in (0,24) for n in counts),
            'event_discrimination':'not_established_single_class' if not event or not non_event else 'both_classes_observed_not_independent',
            'nonoverlap_note':'closed intervals; classwise/era-wise maxima cannot be added as jointly disjoint; disjoint is not independent'}


def alignment(scores,outcomes,direction):
    if direction is None:return None
    a=pd.Series(scores).rank().to_numpy();b=pd.Series(outcomes).rank().to_numpy()
    if len(a)<2 or np.ptp(a)==0 or np.ptp(b)==0:return None
    return float(direction*np.corrcoef(a,b)[0,1])


def rejection_patterns(cells):
    lookup={(c['model'],c['era'],c['horizon'],c['target']):c for c in cells}
    result={}
    for candidate in CANDIDATES:
        alignments=[lookup[(candidate,era,24,TARGETS[0])]['alignment'] for era in ERAS]
        dominated=[]
        for comparator in ('unconditional','context_only',*REFERENCES):
            pairs=[(lookup[(candidate,era,24,target)]['crps'],lookup[(comparator,era,24,target)]['crps']) for era in ERAS for target in TARGETS]
            if all(reference<=score for score,reference in pairs) and any(reference<score for score,reference in pairs):dominated.append(comparator)
        result[candidate]={'negative24m_return_alignment_both_eras':all(a is not None and a<0 for a in alignments),
                           'same_comparator_24m_dominance_both_eras':dominated,
                           'interpretation':'descriptive rejection patterns; absence is not acceptance or significance'}
    return result


def evaluate(prices):
    dataset=build_dataset(prices);rows=dataset['rows'];by_date={r['date']:i for i,r in enumerate(rows)}
    forecasts=[];supports=[]
    for era,(start,end) in ERAS.items():
        dates=pd.date_range(start,end,freq='ME')
        for horizon in PROTOCOL['horizons_months']:
            support=[]
            for date in dates:
                date=date.date().isoformat()
                if date not in by_date:raise ValueError('missing fixed common era origin')
                index=by_date[date];row=rows[index];outcome=row['outcomes'][str(horizon)]
                if outcome['values'] is None or outcome['available']>PROTOCOL['source_cutoff']:
                    raise ValueError('missing fixed common outcome by cutoff')
                forecast=forecast_origin(dataset,index,horizon)
                for k,target in enumerate(TARGETS):
                    atoms=forecast['atoms'][:,k];observed=outcome['values'][k]
                    event=bool(event_mask([observed],target)[0]);train_events=int(event_mask(atoms,target).sum())
                    base={'era':era,'date':date,'horizon':horizon,'target':target,'entry':outcome['entry'],'end':outcome['end'],
                          'label_available':outcome['available'],'event_occurred':event,'training_event_n':train_events}
                    support.append(base)
                    for name,weights in forecast['weights'].items():
                        forecasts.append({**base,'model':name,'score':row['features'].get(name),'outcome':observed,
                            'train_dates':forecast['train_dates'],'last_training_label_available':forecast['last_training_label_available'],
                            'atoms':atoms.tolist(),'weights':weights.tolist(),**forecast['info'][name],
                            'weight_concentration_n':float(1/np.square(weights).sum()),**diagnostics(atoms,weights,observed,target)})
            for target in TARGETS:
                records=[r for r in support if r['target']==target]
                counts=class_support(records)
                if target==TARGETS[0]:
                    counts.update(negative_return_n=counts['event_n'],nonnegative_return_n=counts['non_event_n'])
                supports.append({'era':era,'horizon':horizon,'target':target,'outcome_n':len(records),
                                 'forecast_n':len(records),'support_scope':'fixed era origins; all required to support forecasts',**counts})
    groups={}
    for record in forecasts:groups.setdefault((record['model'],record['era'],record['horizon'],record['target']),[]).append(record)
    cells=[]
    for (model,era,horizon,target),records in groups.items():
        direction=(-1 if target==TARGETS[0] else 1) if model in CANDIDATES else None
        cell={'model':model,'era':era,'horizon':horizon,'target':target,'n':len(records),
              'origins_id':digest([r['date'] for r in records]),
              'alignment':alignment([r['score'] for r in records],[r['outcome'] for r in records],direction)}
        for metric in ('crps','brier','coverage_50','coverage_80','width_50','width_80','outside_atom_range','fallback','cell_n','weight_concentration_n'):
            cell[metric]=float(np.mean([r[metric] for r in records]))
        cells.append(cell)
    lookup={(c['model'],c['era'],c['horizon'],c['target']):c for c in cells}
    for cell in cells:
        for comparator in ('unconditional','context_only'):
            reference=lookup[(comparator,cell['era'],cell['horizon'],cell['target'])]
            if cell['origins_id']!=reference['origins_id']:raise ValueError('comparison support differs')
            for loss in ('crps','brier'):
                denominator=reference[loss]
                cell[f'{loss}_skill_vs_{comparator}']=100*(1-cell[loss]/denominator) if denominator>0 else None
                cell[f'{loss}_skill_status_vs_{comparator}']='defined' if denominator>0 else 'undefined_zero_reference_loss'
    return {'protocol':PROTOCOL,'dataset_id':digest(dataset),'cells':cells,'class_support':supports,
            'rejection_patterns':rejection_patterns(cells),'predictions':forecasts}


def run(source,registration_path,output):
    registered=json.loads(Path(registration_path).read_bytes())
    if registered!=registration():raise ValueError('registration/code/data/runtime identity mismatch')
    output=safe_path(Path(output));private=safe_path(PRIVATE_ROOT)
    if not output.is_relative_to(private) or output==private:raise ValueError('derived provider outputs must remain in ignored private directory')
    output.mkdir(parents=True,exist_ok=False)
    publish(output/'request.json',canonical_bytes({'registration':registered,'source':str(source),'privacy':'derived numeric outputs remain private'}))
    try:
        with Path(source).open('rb') as stream:payload=stream.read(2*1024*1024+1)
        if len(payload)>2*1024*1024 or sha(payload)!=registered['source_sha256']:raise ValueError('source size/hash mismatch')
        frame=pd.read_csv(io.BytesIO(payload),parse_dates=['Date'])
        if len(frame)!=registered['source_rows']:raise ValueError('source row count mismatch')
        prices=frame.set_index('Date')['market_total_return_index']
        if str(prices.index[0].date())!=registered['source_first_month'] or str(prices.index[-1].date())!=registered['source_last_month']:
            raise ValueError('source coverage mismatch')
        result=evaluate(prices)
        result['registration_id']=registered['registration_id'];result['source_sha256']=sha(payload)
        write_packet(output,{'result.json':canonical_bytes(result)},bound_existing=('request.json',))
    except Exception as error:
        publish(output/'error.json',canonical_bytes({'error':str(error),'status':'failed_no_discard_or_retuning'}));raise
    return {'status':'monthly_portability_falsification_only','output':str(output),'registration_id':registered['registration_id']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['register','run'])
    p.add_argument('--registration',type=Path,required=True);p.add_argument('--source',type=Path);p.add_argument('--output-dir',type=Path)
    a=p.parse_args()
    if a.command=='register':
        publish(a.registration,canonical_bytes(registration()));print('Registration written; no provider observations read or scored.')
    else:print(json.dumps(run(a.source,a.registration,a.output_dir)))

if __name__=='__main__':main()
