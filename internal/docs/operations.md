# Operations and Outputs

## Run Commands

### Pipeline

```bash
python main.py
```

### Backfill Helpers

```bash
python backfill.py
python backfill.py --target btc-price
python backfill.py --target total-market
python backfill.py --target social
python backfill.py --target onchain
```

### Validation

```bash
python validate.py
```

### Publish Web Artifacts

```bash
python publish_web.py
```

Validation warnings do not block export. Hard validation failures exit non-zero.

## Main Output Files

- `output/risk_scores_full.csv`
- `output/latest_scores.csv`
- `output/feature_frames/*.csv`
- `output/category_breakdowns/{btc,total_market}.csv`
- `output/metric_breakdowns/{btc,total_market}.csv`
- `output/metric_health.csv`
- `output/source_health.csv`
- `output/source_modes.csv`
- `output/sanity_report.csv`
- `output/cycle_feature_snapshots_monthly.csv`
- `output/cycle_regime_scores_monthly.csv`
- `output/cycle_signal_decisions_monthly.csv`
- `output/cycle_backtest_report.csv`
- `output/financial_benchmark_summary.csv`
- `output/financial_benchmark_curves_monthly.csv`

## Web Contract (`data/web/v2`)

- `manifest.json`
- `latest_snapshot.json`
- `history_core.json`
- `category_breakdowns_btc.json`
- `category_breakdowns_total_market.json`
- `metric_breakdowns_btc.json`
- `metric_breakdowns_total_market.json`
- `diagnostics.json`

Contract guarantees:

- Stable score keys and confidence keys.
- Stable ISO date/timestamp formatting.
- Explicit source mode and source-health diagnostics.
