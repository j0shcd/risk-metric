"""Fixed real-yield tightening state. Reconstruction only; no fitted parameters.

Observation dates plus a declared lag are not actual release/vintage timestamps.
Only raw macro observations at or before each lagged anchor reach the score.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
import numpy as np
import pandas as pd

CONFIG = {'candidate_id':'real_yield_tightening_12m_lag45',
          'source_file':'fred_real_yield_10y.csv','source_column':'real_yield_10y',
          'lag_calendar_days':45,'change_calendar_months':12,'maximum_endpoint_age_days':14,
          'scale_percentage_points':1.0,'neutral_score':50.0,
          'first_origin':'2014-12-31','last_origin':'2022-12-31','direction':'higher_risk'}


def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(value):return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def generate(frame, origins):
    """Pure dated producer; missing/stale endpoints emit neutral plus a reason."""
    dates=pd.DatetimeIndex(pd.to_datetime(frame['Date'],errors='raise'))
    values=pd.to_numeric(frame[CONFIG['source_column']],errors='raise').to_numpy(dtype=float)
    if (dates.hasnans or dates.tz is not None or not dates.equals(dates.normalize())
            or dates.has_duplicates or not dates.is_monotonic_increasing or np.isinf(values).any()):
        raise ValueError('source requires unique increasing naive daily dates and finite-or-missing yields')
    origins=pd.DatetimeIndex(origins)
    if (origins.hasnans or origins.tz is not None or not origins.equals(origins.normalize())
            or origins.has_duplicates or not origins.is_monotonic_increasing
            or any(d!=d+pd.offsets.MonthEnd(0) for d in origins)):
        raise ValueError('origins require unique increasing completed month-end dates')
    valid=np.isfinite(values);dates=dates[valid];values=values[valid]
    rows=[]
    for decision in origins:
        cutoff=decision-pd.Timedelta(days=CONFIG['lag_calendar_days'])
        prior=cutoff-pd.DateOffset(months=CONFIG['change_calendar_months'])
        row={'Date':decision.date().isoformat(),'monetary_risk':CONFIG['neutral_score'],
             'cutoff':cutoff.date().isoformat(),'prior_anchor':prior.date().isoformat(),
             'current_observation':None,'prior_observation':None,'current_yield_pp':None,
             'prior_yield_pp':None,'change_pp':None,'status':'neutral_missing_endpoint'}
        endpoints=[]
        for label,anchor in (('current',cutoff),('prior',prior)):
            position=dates.searchsorted(anchor,side='right')-1
            if position<0:endpoints.append(None);continue
            observed=dates[position];value=float(values[position])
            row[label+'_observation']=observed.date().isoformat();row[label+'_yield_pp']=value
            endpoints.append((observed,value,(anchor-observed).days))
        if all(e is not None for e in endpoints):
            if any(e[2]>CONFIG['maximum_endpoint_age_days'] for e in endpoints):
                row['status']='neutral_stale_endpoint'
            else:
                change=endpoints[0][1]-endpoints[1][1]
                if not np.isfinite(change):raise ValueError('yield difference outside finite numeric domain')
                row.update(change_pp=change,monetary_risk=float(50+50*np.tanh(change/CONFIG['scale_percentage_points'])),status='observed')
        rows.append(row)
    return pd.DataFrame(rows)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--config',type=Path,default=Path(__file__).with_name('config.json'))
    parser.add_argument('--output-dir',type=Path,required=True);args=parser.parse_args(argv)
    config_raw=args.config.read_bytes()
    if json.loads(config_raw)!=CONFIG:raise ValueError('only the preregistered fixed specification is permitted')
    manifest_raw=(args.bundle/'manifest.json').read_bytes();manifest=json.loads(manifest_raw)
    raw=(args.bundle/CONFIG['source_file']).read_bytes()
    if manifest['cutoff']!='2022-12-31' or manifest['sources'][CONFIG['source_file']]['development_sha256']!=sha(raw):
        raise ValueError('development source hash/cutoff mismatch')
    frame=pd.read_csv(io.BytesIO(raw),usecols=['Date',CONFIG['source_column']],na_values=['.'])
    if len(frame) and pd.to_datetime(frame['Date']).max()>pd.Timestamp(CONFIG['last_origin']):
        raise ValueError('development source contains post-cutoff observations')
    origins=pd.date_range(CONFIG['first_origin'],CONFIG['last_origin'],freq='ME')
    features=generate(frame,origins)
    if len(features)!=97 or not np.isfinite(features['monetary_risk']).all():
        raise ValueError('all 97 registered origins must have finite scores')
    csv=features[['Date','monetary_risk']].to_csv(index=False).encode()
    # Exclusive output files: generation cannot silently replace a registered packet.
    target=args.output_dir.resolve();target.mkdir(exist_ok=False)
    payloads={'candidate.csv':csv,'features.csv':features.to_csv(index=False).encode(),'config.json':config_raw,
              'manifest.json':canonical({'candidate_id':CONFIG['candidate_id'],'status':'frozen_spec_unscored',
                  'training':'none; no fitted transformations or label updates',
                  'source_sha256':sha(raw),'bundle_manifest_sha256':sha(manifest_raw),
                  'producer_sha256':sha(Path(__file__).read_bytes()),'config_sha256':sha(config_raw),
                  'candidate_csv_sha256':sha(csv),'rows':len(features),
                  'status_counts':features['status'].value_counts().to_dict(),
                  'limitations':'Reconstructed cache; observation/release/UTC-close/vintages unverified. Lag is not PIT proof.'})}
    for name,payload in payloads.items():
        with (target/name).open('xb') as stream:stream.write(payload)
    print(json.dumps({'output':str(target),'rows':len(features),'status_counts':features['status'].value_counts().to_dict()}))

if __name__=='__main__':main()
