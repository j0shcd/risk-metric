"""Frozen price-generative forecast replay; no model fitting choices or promotion.

The caller registers two seeds, exact model/readout/source/reference identities,
and sample count before execution. Only 731 closes through a query reach fit().
Simulation must include next-day entry, then calendar holding days; model API
owns path generation. Primary generative losses estimate the underlying predictive law with iid-draw
U-statistic CRPS and fair Brier. Issued reference CDFs remain uncorrected.
Replicas diagnose simulation variation, not significance.
"""
from __future__ import annotations

import argparse
from dataclasses import fields, is_dataclass
import hashlib
import importlib
import json
from pathlib import Path
import platform

import numpy as np
import pandas as pd

from .market_dataset import COMPONENTS, TARGETS, build_dataset, canonical_bytes, digest, load_snapshot
from .market_information import ROLES, PROTOCOL as REFERENCE_PROTOCOL, _role
from .readout_study import diagnostics, event_mask
from .scorecard_artifacts import publish, safe_path, write_packet

PROTOCOL = {
    'name': 'generative-price-scorecard-v2', 'horizons': [12, 24, 48],
    'lookback_closes': 731, 'fit_returns': 730, 'replicas': 2,
    'events': 'return<0; entry loss>log(2); peak drawdown>log(2)',
    'intervals': 'inclusive central 50% and 80%; left inverse weighted empirical CDF',
    'entry': 'next calendar day; first simulated return updates state but is excluded from holding P&L',
    'development_cutoff': '2022-12-31', 'outer_start': '2023-01-01',
    'supports': ['matched_direct_cdf', 'all_generative_eligible'],
    'failure_policy': 'retain all eligible origins; withhold cell means if any forecast fails',
    'ensemble_interpretation': 'iid_predictive_law_draws',
    'crps_estimand': 'generative iid U-statistic uses n*(n-1) pair denominator; reference issued CDF exact uncorrected',
    'brier_estimand': 'generative empirical Brier minus p*(1-p)/(n-1); reference issued CDF uncorrected',
    'corrections': 'empirical scores and corrections retained; no clipping of corrected scores',
    'method_sources': ['https://empslocal.ex.ac.uk/people/staff/ferro/Publications/ferro2013.pdf',
                       'https://scoringrules.readthedocs.io/en/latest/crps_estimators.html'],
}
METRICS = ('crps', 'brier', 'empirical_crps', 'crps_mc_correction', 'empirical_brier', 'brier_mc_correction', 'coverage_50', 'coverage_80', 'width_50', 'width_80', 'outside_atom_range')
CODE_FILES = ('generative_forecast_scorecard.py', 'market_dataset.py', 'market_information.py',
              'readout_study.py', 'distribution_readout.py')


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def code_identity():
    return {name: sha(Path(__file__).with_name(name).read_bytes()) for name in CODE_FILES}


def array_identity(array):
    array = np.ascontiguousarray(array)
    return {'shape': list(array.shape), 'dtype': array.dtype.str, 'sha256': sha(array.tobytes())}


def posterior_identity(posterior):
    """Hash arrays without archiving large grids; deterministic refit regenerates them."""
    if not is_dataclass(posterior):
        raise ValueError('fit must return a posterior dataclass')
    state = {}
    for field in fields(posterior):
        value = getattr(posterior, field.name)
        if isinstance(value, np.ndarray):
            if not np.isfinite(value).all(): raise ValueError('nonfinite posterior state')
            state[field.name] = array_identity(value)
        else:
            canonical_bytes(value)  # reject nonserializable/nonfinite diagnostics
            state[field.name] = json.loads(canonical_bytes(value))
    return {'state': state, 'state_sha256': digest(state)}


def simulation_seed(base, date):
    # Do not seed from the full snapshot identity: future suffixes must not alter draws.
    return int.from_bytes(hashlib.sha256(f'{base}:{date}'.encode()).digest()[:8], 'big')


def distribution_summary(atoms, weights, target, observed=None, *, interpretation="issued_cdf"):
    if interpretation not in ("issued_cdf", "iid_predictive_law_draws"):
        raise ValueError("unsupported ensemble interpretation")
    atoms, weights = np.asarray(atoms, float), np.asarray(weights, float)
    if (atoms.ndim != 1 or atoms.shape != weights.shape or not len(atoms)
            or not np.isfinite(atoms).all() or not np.isfinite(weights).all()
            or (weights < 0).any() or not np.isclose(weights.sum(), 1, rtol=0, atol=1e-12)
            or (target != 'terminal_log_return' and (atoms < 0).any())):
        raise ValueError('invalid predictive atoms/weights')
    if interpretation == 'iid_predictive_law_draws' and (len(atoms) < 2 or not np.array_equal(weights, np.full(len(atoms),1/len(atoms)))):
        raise ValueError('fair scores require equally weighted iid draws and n>=2')
    order = np.argsort(atoms); x, w = atoms[order], weights[order]
    cumulative = np.cumsum(w)
    def quantile(q): return float(x[min(np.searchsorted(cumulative, q), len(x)-1)])
    result = {'score_interpretation': interpretation, 'sample_n': len(atoms), 'unique_atom_n': len(np.unique(atoms)),
              'atom_min': float(x[0]), 'atom_max': float(x[-1]),
              'effective_weight_n': float(1 / np.square(weights).sum()),
              'atoms_identity': array_identity(atoms), 'weights_identity': array_identity(weights),
              'event_probability': float(weights @ event_mask(atoms, target)),
              'intervals': {str(level): [quantile(tail), quantile(1-tail)] for level, tail in ((50,.25),(80,.1))}}
    if observed is not None:
        result.update(diagnostics(atoms, weights, observed, target))
        result.update(empirical_crps=result['crps'], empirical_brier=result['brier'],
                      crps_mc_correction=0., brier_mc_correction=0.)
        if interpretation == 'iid_predictive_law_draws':
            n = len(x)
            previous_w = np.cumsum(w) - w
            previous_wx = np.cumsum(w*x) - w*x
            spread = float(np.sum(w * (x*previous_w-previous_wx)))
            result['crps_mc_correction'] = spread/(n-1)
            p = result['event_probability']
            result['brier_mc_correction'] = p*(1-p)/(n-1)
            result['crps'] = float(np.mean(np.abs(atoms-observed)) - n*spread/(n-1))
            result['brier'] = result['empirical_brier'] - result['brier_mc_correction']
        if not np.isfinite([result[name] for name in METRICS]).all():
            raise ValueError('nonfinite forecast loss')
    return result


def _price_rows(snapshot):
    dates = pd.DatetimeIndex([r['date'] for r in snapshot['daily']])
    if dates.empty or not dates.equals(pd.date_range(dates[0], dates[-1], freq='D')):
        raise ValueError('snapshot must retain every daily date')
    monthly = [{'date': d.date().isoformat(), **{name: None for name in COMPONENTS}}
               for d in pd.date_range(dates[0], dates[-1], freq='ME')]
    price_snapshot = {'daily': snapshot['daily'], 'monthly': monthly}
    rows = build_dataset(price_snapshot, PROTOCOL['horizons'])['rows']
    price = np.array([np.nan if r['price'] is None else r['price'] for r in snapshot['daily']], float)
    return dates, price, rows


def _reference_maps(snapshot, references, by_date):
    """Validate immutable direct-CDF forecasts, never refit or relabel them."""
    if not references: raise ValueError('frozen direct-CDF reference forecasts required')
    dataset_id = digest(build_dataset(snapshot, PROTOCOL['horizons']))
    expected_code = {name: sha(Path(__file__).with_name(name).read_bytes())
                     for name in ('market_information.py', 'market_dataset.py', 'market_scorecard.py', 'distribution_readout.py')}
    as_of = snapshot['daily'][-1]['date']; maps = {}; common = None
    for reference in references:
        if (reference['source_sha256'] != snapshot.get('source_sha256')
                or reference['dataset_id'] != dataset_id or reference['protocol'] != REFERENCE_PROTOCOL
                or reference['code_sha256'] != expected_code
                or reference['as_of'] != as_of or reference['minimum_training'] != 24
                or reference['development_cutoff'] != PROTOCOL['development_cutoff']
                or reference['outer_start'] != PROTOCOL['outer_start']):
            raise ValueError('frozen reference identity/protocol mismatch')
        name = 'direct_cdf:' + reference['candidate_name']
        if name in maps: raise ValueError('duplicate reference name')
        records = {}
        for record in reference['predictions']:
            key = (record['date'], record['horizon'], record['target'])
            if key in records or record['horizon'] not in PROTOCOL['horizons'] or record['target'] not in TARGETS:
                raise ValueError('duplicate/unsupported reference forecast')
            row = by_date[record['date']]; outcome = row['outcomes'][str(record['horizon'])]
            role = _role(row, outcome, as_of, PROTOCOL['development_cutoff'], PROTOCOL['outer_start'])
            observed = outcome['values'][TARGETS.index(record['target'])] if role not in ('pending','outcome_unavailable') else None
            if (record['role'] != role or record['outcome'] != observed or record['entry'] != outcome['entry']
                    or record['end'] != outcome['end'] or record['label_available'] != outcome['available']):
                raise ValueError('reference outcome/availability differs from frozen price path')
            records[key] = record
        support = set(records)
        if any((date, horizon, target) not in support for date,horizon,_ in support for target in TARGETS):
            raise ValueError('reference target vector incomplete')
        if common is not None and common != support:
            raise ValueError('references must share exact forecast support')
        common = support; maps[name] = records
    return maps, common


def evaluate(snapshot, references, model, registration):
    if registration['protocol'] != PROTOCOL: raise ValueError('scorecard protocol mismatch')
    if registration['ensemble_interpretation'] != 'iid_predictive_law_draws':
        raise ValueError('fair score correction requires declared iid path draws')
    seeds = registration['replica_seeds']; paths = registration['sample_count']
    if (not isinstance(seeds, list) or len(seeds) != 2 or len(set(seeds)) != 2
            or any(type(s) is not int or s < 0 for s in seeds)
            or type(paths) is not int or paths < 2):
        raise ValueError('two distinct nonnegative seeds and declared sample count required')
    if registration['model_protocol'] != model.PROTOCOL: raise ValueError('model protocol mismatch')
    if model.PROTOCOL['paths'] != paths: raise ValueError('registered sample count differs from model')
    dates, prices, rows = _price_rows(snapshot); by_date = {r['date']: r for r in rows}
    reference_maps, reference_support = _reference_maps(snapshot, references, by_date)
    as_of = snapshot['daily'][-1]['date']; records = []; fit_records = []; eligibility = []
    eligible_keys = set()
    for row in rows:
        position = dates.get_indexer([pd.Timestamp(row['date'])])[0]
        closes = prices[max(0,position-730):position+1]
        eligible = len(closes)==731 and np.isfinite(closes).all() and (closes>0).all()
        eligibility.append({'date': row['date'], 'eligible': bool(eligible),
                            'reason': None if eligible else 'requires_731_consecutive_valid_closes'})
        if not eligible: continue
        for horizon in PROTOCOL['horizons']:
            for target in TARGETS: eligible_keys.add((row['date'],horizon,target))
        returns = np.diff(np.log(closes))
        fit_record = {'date': row['date'], 'first_close': dates[position-730].date().isoformat(),
                      'last_close': row['date'], 'closes_identity': array_identity(closes),
                      'returns_identity': array_identity(returns), 'status': 'ok'}
        posterior = None
        try:
            posterior = model.fit(returns.copy())
            fit_record.update(posterior_identity(posterior))
        except Exception as error:
            posterior = None
            fit_record.update(status='fit_failed', error=f'{type(error).__name__}: {error}')
        fit_record['fit_id'] = digest(fit_record); fit_records.append(fit_record)
        holding_days = [(pd.Timestamp(row['outcomes'][str(h)]['end']) - pd.Timestamp(row['outcomes'][str(h)]['entry'])).days
                        for h in PROTOCOL['horizons']]
        for replica, base_seed in enumerate(seeds):
            seed = simulation_seed(base_seed, row['date']); failure = None; samples = None
            if posterior is None: failure = fit_record.get('error', 'fit_failed')
            else:
                try:
                    if posterior_identity(posterior)['state_sha256'] != fit_record['state_sha256']:
                        raise ValueError('posterior changed before simulation')
                    samples = np.asarray(model.simulate(posterior, holding_days, seed=seed), float)
                    if posterior_identity(posterior)['state_sha256'] != fit_record['state_sha256']:
                        raise ValueError('simulation mutated frozen posterior')
                    if samples.shape != (paths,3,3) or not np.isfinite(samples).all() or (samples[:,:,1:] < 0).any():
                        raise ValueError('invalid sample shape, nonfinite or negative path-loss atoms')
                except Exception as error:
                    failure = f'{type(error).__name__}: {error}'
            for h_index, horizon in enumerate(PROTOCOL['horizons']):
                outcome = row['outcomes'][str(horizon)]
                role = _role(row, outcome, as_of, PROTOCOL['development_cutoff'], PROTOCOL['outer_start'])
                for t_index,target in enumerate(TARGETS):
                    observed = outcome['values'][t_index] if role not in ('pending','outcome_unavailable') else None
                    record = {'model':'generative', 'date':row['date'], 'horizon':horizon, 'target':target,
                              'role':role, 'replica':replica, 'seed':seed, 'fit_id':fit_record['fit_id'],
                              'holding_days':holding_days[h_index], 'entry':outcome['entry'], 'end':outcome['end'],
                              'label_available':outcome['available'], 'outcome':observed,
                              'matched_direct_cdf': (row['date'],horizon,target) in reference_support,
                              'status': 'numerical_failure' if failure else 'scored' if observed is not None else 'unscored'}
                    if failure: record['error'] = failure
                    else:
                        try: record.update(distribution_summary(samples[:,h_index,t_index], np.full(paths,1/paths),target,observed,interpretation='iid_predictive_law_draws'))
                        except Exception as error:
                            record.update(status='numerical_failure', error=f'{type(error).__name__}: {error}')
                    records.append(record)
    # Only matched eligible origins get reference comparisons. Additional generative
    # coverage is reported separately, never pooled into superiority comparisons.
    for name, mapping in reference_maps.items():
        for key in sorted(eligible_keys.intersection(mapping)):
            original = mapping[key]
            record = {'model':name, 'date':key[0], 'horizon':key[1], 'target':key[2], 'replica':None,
                      'role':original['role'], 'outcome':original['outcome'], 'matched_direct_cdf':True,
                      'status':'scored' if original['outcome'] is not None else 'unscored'}
            record.update(distribution_summary(original['atoms'], original['candidate_weights'],key[2],original['outcome']))
            if original['outcome'] is not None and not np.isclose(record['crps'],original['candidate_crps'],rtol=0,atol=1e-12):
                raise ValueError('frozen reference CRPS verification failed')
            records.append(record)
    first = next(iter(reference_maps.values()))
    for name, weight_field in [('unconditional',None),('context','reference_weights')]:
        for key in sorted(eligible_keys.intersection(first)):
            original=first[key]; atoms=original['atoms']
            weights=np.full(len(atoms),1/len(atoms)) if weight_field is None else original[weight_field]
            record={'model':name,'date':key[0],'horizon':key[1],'target':key[2],'replica':None,
                    'role':original['role'],'outcome':original['outcome'],'matched_direct_cdf':True,
                    'status':'scored' if original['outcome'] is not None else 'unscored'}
            record.update(distribution_summary(atoms,weights,key[2],original['outcome'])); records.append(record)
    cells = aggregate(records, [*reference_maps, "unconditional", "context"])
    return {'protocol':PROTOCOL, 'registration':registration, 'snapshot_id':digest(snapshot),
            'source_sha256':snapshot.get('source_sha256'), 'as_of':as_of, 'code_sha256':code_identity(),
            'reference_identity':digest(references), 'model_protocol':model.PROTOCOL,
            'runtime':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__},
            'eligibility':eligibility, 'fits':fit_records, 'records':records, 'cells':cells,
            'replica_stability':replica_stability(cells),
            'limitations':['Public-history pseudo-out-of-sample reconstruction, not prospective evidence.',
                           'Publication/vintages and UTC close convention remain unverified.',
                           'Extra generative coverage has no new-origin comparator.',
                           'Two simulation replicas diagnose Monte Carlo variation, not an uncertainty interval or significance.',
                           'Fair generative scores require iid path draws; correlated draws invalidate the correction.',
                           'Numerical failures are retained; incomplete-support mean scores are withheld.',
                           'No combined metric, model selection, financial utility or promotion.']}


def aggregate(records, reference_names=()):
    groups={}
    for record in records:
        supports = ['matched_direct_cdf'] if record['matched_direct_cdf'] else []
        if record['model']=='generative': supports.append('all_generative_eligible')
        for support in supports:
            key=(support,record['model'],record['replica'],record['role'],record['horizon'],record['target'])
            groups.setdefault(key,[]).append(record)
    for support in PROTOCOL['supports']:
        model_replicas = [('generative',0),('generative',1)]
        if support == 'matched_direct_cdf': model_replicas += [(name,None) for name in reference_names]
        for model,replica in model_replicas:
            for role in ROLES:
                for horizon in PROTOCOL['horizons']:
                    for target in TARGETS: groups.setdefault((support,model,replica,role,horizon,target),[])
    cells=[]
    for (support,model,replica,role,horizon,target), group in groups.items():
        failed=[r for r in group if r['status']=='numerical_failure']; scored=[r for r in group if r['status']=='scored']
        cell={'support':support,'model':model,'replica':replica,'role':role,'horizon':horizon,'target':target,
              'requested_n':len(group),'scored_n':len(scored),'failure_n':len(failed),
              'origins_id':digest(sorted(r['date'] for r in group)),
              'means':{name:float(np.mean([r[name] for r in scored])) if scored and not failed else None for name in METRICS},
              'successful_subset_diagnostic':{name:float(np.mean([r[name] for r in scored])) if scored else None for name in METRICS}}
        successes=[r for r in group if r['status']!='numerical_failure']
        cell['forecast_diagnostics']={
            'successful_forecast_n':len(successes),
            'sample_n_range':[min(r['sample_n'] for r in successes),max(r['sample_n'] for r in successes)] if successes else None,
            'atom_min':min(r['atom_min'] for r in successes) if successes else None,
            'atom_max':max(r['atom_max'] for r in successes) if successes else None,
            'mean_unique_atom_n':float(np.mean([r['unique_atom_n'] for r in successes])) if successes else None,
        }
        cells.append(cell)
    return cells


def replica_stability(cells):
    by_key={}; result=[]
    for cell in cells:
        if cell['model']=='generative':
            key=(cell['support'],cell['role'],cell['horizon'],cell['target'])
            by_key.setdefault(key,{})[cell['replica']]=cell
    for (support,role,horizon,target), replicas in by_key.items():
        a,b=replicas[0],replicas[1]
        result.append({'support':support,'role':role,'horizon':horizon,'target':target,
                       'replica_failure_counts':[a['failure_n'],b['failure_n']],
                       'absolute_mean_differences':{name:abs(a['means'][name]-b['means'][name])
                                                   if a['means'][name] is not None and b['means'][name] is not None else None
                                                   for name in METRICS}})
    return result


def readable(result, support):
    lines=[f'# Generative forecast scorecard: {support}', '',
           'Fixed target/horizon/role/replica cells. No combined winner. Incomplete-support means are withheld.',
           'Extra eligible origins are not evidence of superiority. Two replicas are Monte Carlo diagnostics.',
           'Primary generative CRPS/Brier are iid-draw unbiased estimates; reference CDF scores are exact and uncorrected.',
           'Empirical scores and corrections remain in JSON; corrected scores are not clipped.', '',
           '| Role | Months | Target | Model | Replica | Requested / scored / failed | CRPS | Brier | 50% cover / width | 80% cover / width |',
           '|---|---:|---|---|---:|---:|---:|---:|---|---|']
    def show(value):return '—' if value is None else f'{value:.6f}'
    for c in result['cells']:
        if c['support']!=support:continue
        m=c['means'];lines.append(f"| {c['role']} | {c['horizon']} | {c['target']} | {c['model']} | {c['replica']} | {c['requested_n']} / {c['scored_n']} / {c['failure_n']} | {show(m['crps'])} | {show(m['brier'])} | {show(m['coverage_50'])} / {show(m['width_50'])} | {show(m['coverage_80'])} / {show(m['width_80'])} |")
    return ('\n'.join(lines)+'\n').encode()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--reference-replay',type=Path,required=True)
    parser.add_argument('--registration',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args(argv);target=safe_path(args.output_dir);target.mkdir(exist_ok=False)
    raw=args.registration.read_bytes(); registration=json.loads(raw)
    publish(target/'request.json',canonical_bytes({'source':str(args.source),'reference_replay':str(args.reference_replay),'registration':str(args.registration)}))
    try:
        source=args.source.read_bytes();reference=args.reference_replay.read_bytes()
        if sha(source)!=registration['source_sha256'] or sha(reference)!=registration['reference_replay_sha256']:
            raise ValueError('registered input hash mismatch')
        if registration['scorecard_code_sha256']!=code_identity():raise ValueError('registered scorecard code mismatch')
        model=importlib.import_module(registration['model_module'])
        if sha(Path(model.__file__).read_bytes())!=registration['model_source_sha256']:
            raise ValueError('registered model source mismatch')
        snapshot=load_snapshot(args.source)
        if snapshot['source_sha256']!=sha(source):raise ValueError('source changed while loading')
        result=evaluate(snapshot,json.loads(reference)['references'],model,registration)
    except Exception as error:
        write_packet(target,{'error.json':canonical_bytes({'status':'ineligible','error':f'{type(error).__name__}: {error}'})},bound_existing=('request.json',))
        raise
    write_packet(target,{'registration.json':raw,'scorecard.json':canonical_bytes(result),
                        **{support+'.md':readable(result,support) for support in PROTOCOL['supports']}},bound_existing=('request.json',))
    print(json.dumps({'status':'retrospective_research_no_promotion','output':str(target)}));return 0


if __name__=='__main__':raise SystemExit(main())
