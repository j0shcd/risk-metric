"""Frozen upside gain concentration; causal price-only research candidate."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

PARAMETERS = {'window_daily_returns': 730, 'no_upside_risk': 0.0, 'missing_risk': 0.5}
COLUMN = 'astra_b_upside_concentration'


def generate(frame: pd.DataFrame, dates=None) -> pd.DataFrame:
    """Month-end state from exactly731 consecutive closes ending at query.

    Missing/stale/invalid windows are neutral and flagged, never interpolated.
    No targets, fitting or history-wide scaling. UTC close vintage unverified.
    """
    observed = pd.DatetimeIndex(pd.to_datetime(frame['Date'], utc=True)).tz_localize(None)
    if observed.hasnans or observed.has_duplicates or not observed.is_monotonic_increasing or not observed.equals(observed.normalize()):
        raise ValueError('dates must be ordered unique UTC calendar days')
    prices = pd.Series(pd.to_numeric(frame['Price'], errors='raise').to_numpy(dtype=float),index=observed)
    if dates is None:
        dates = pd.date_range(observed.min(),observed.max(),freq='ME') if len(observed) else pd.DatetimeIndex([])
    queries = pd.DatetimeIndex(pd.to_datetime(dates,utc=True)).tz_localize(None)
    if queries.hasnans or queries.has_duplicates or not queries.is_month_end.all() or not queries.equals(queries.normalize()):
        raise ValueError('queries must be unique month-end calendar days')
    window = PARAMETERS['window_daily_returns'];values=[]
    for query in queries:
        expected=pd.date_range(end=query,periods=window+1,freq='D')
        p=prices.reindex(expected).to_numpy()
        if not np.isfinite(p).all() or (p<=0).any():
            score=PARAMETERS['missing_risk'];status='neutral_missing_or_invalid_window'
        else:
            gains=np.maximum(np.diff(np.log(p)),0.)
            maximum=gains.max();status='valid'
            if maximum==0:
                score=PARAMETERS['no_upside_risk'];status='valid_no_upside_prior'
            else:
                scaled=gains/maximum
                concentration=np.dot(scaled,scaled)/scaled.sum()**2
                score=float(np.clip((window*concentration-1)/(window-1),0.,1.))
        values.append((query,score,status))
    return pd.DataFrame(values,columns=['Date',COLUMN,'status']).set_index('Date')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=generate(pd.read_csv(args.inputs/'btc_daily.csv'))
    with args.output.open('x') as stream:result.to_csv(stream)

if __name__=='__main__':main()
