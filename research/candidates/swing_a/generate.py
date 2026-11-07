"""Generate the three preregistered slow-anchor occupancy variants."""
import argparse
from pathlib import Path

import pandas as pd

from .indicator import generate_indicator


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    frame = pd.read_csv(args.bundle / 'btc_daily.csv')
    if pd.to_datetime(frame.Date).max() > pd.Timestamp('2022-12-31'):
        raise ValueError('development producer cannot consume post-2022 rows')
    variants = {f'swing_a_memory_{suffix}': generate_indicator(frame, memory_weight=weight)
                for suffix, weight in [('0', 0.0), ('50', 0.5), ('100', 1.0)]}
    result = pd.DataFrame(variants).rename_axis('Date')
    with args.output.open('x') as handle:
        result.to_csv(handle, float_format='%.17g')


if __name__ == '__main__':
    main()
