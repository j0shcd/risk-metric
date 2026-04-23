# risk-metric

Modernized crypto risk engine focused on market heat and attention monitoring.

This project does **not** attempt to generate buy/sell signals. It produces directional heat and attention metrics that highlight unusual market conditions.

## Outputs

The pipeline produces:

1. `btc_risk` (`heat`, `attention`, `confidence`, `coverage`)
2. `total_market_risk` (`heat`, `attention`, `confidence`, `coverage`)
3. `headline_attention = 0.7 * btc_attention + 0.3 * total_attention`
4. `headline_direction = 0.7 * btc_heat + 0.3 * total_heat`
5. `confidence_score`

Heat is bounded to `[-1, 1]`, attention to `[0, 1]`.

## Design

Pipeline layers:

- `sources` -> data retrieval and fallback handling
- `features` -> raw indicator construction
- `normalization` -> rolling winsorized robust-z to bounded signal + 7D smoothing
- `scoring` -> weighted category aggregation with availability and reliability controls
- `outputs` -> CSV exports and validation checks

Validation includes:

- score bounds checks
- recent-signal presence checks
- staleness checks on key output columns
- source health and metric health availability checks
- source contract checks (duplicates, monotonic timestamps, numeric validity, source-specific staleness thresholds)
- walk-forward sanity checks (tops, bottoms, sideways, forward-return relationship)

## v1 Indicator Coverage

- Price structure:
  - BTC `50d/350d` trend extension
  - BTC running `1Y ROI`
  - BTC log-regression deviation
- Total market context:
  - Total market cap trend extension
  - Total market cap running `1Y ROI`
  - Total market cap log-regression deviation
  - BTC dominance proxy
  - Local `total_marketcap.csv` is maintained over time (historical APIs when available, otherwise daily free global snapshot append)
- On-chain:
  - MVRV Z-score
  - Puell Multiple
  - Supply in profit / implied loss
- Sentiment/social:
  - Fear & Greed index
  - YouTube activity basket
  - Google Trends proxy (fallback CSV when official API unavailable)
  - Coinbase app-rank proxy (experimental, kill-switch enabled)

## Weighting

Fixed category weights:

- On-chain: `30%`
- Price structure: `30%`
- Total market context: `20%`
- Social: `15%`
- Fear & Greed: `5%`

Missing metric behavior:

- Reweight within category among available metrics.
- If category coverage drops below `50%`, category contribution is damped.
- Confidence combines coverage and reliability.

## Running

### 1) Run main pipeline

```bash
python main.py
```

### 2) Backfill / refresh outputs

```bash
python backfill.py
```

### 3) Refresh total market cap local store only

```bash
python backfill_total_marketcap.py
```

### 4) Refresh social local stores only

```bash
python backfill_social.py
```

### 5) Refresh on-chain local store only

```bash
python backfill_onchain.py
```

### 6) Validate output health

```bash
python validate.py
```

## Configuration

Configuration is loaded from:

1. `config/runtime.json` (optional)
2. environment variables (override file values)

Use `config/runtime.example.json` as a template.

Important env vars:

- `GLASSNODE_API_KEY`
- `CMC_API_KEY`
- `COINGECKO_API_KEY`
- `YOUTUBE_API_KEY`
- `YOUTUBE_CHANNEL_IDS` (comma-separated)
- `TOTAL_MARKETCAP_CSV` (local history store for total market cap)
- `ONCHAIN_FALLBACK_CSV` (local history store for on-chain metrics)
- `YOUTUBE_FALLBACK_CSV` (local history store for youtube interest)
- `APPLE_APP_STORE_COUNTRY` (default: `us`)
- `COINBASE_IOS_APP_ID` (default: `886427730`)
- `GOOGLE_TRENDS_CSV` (fallback path)
- `COINBASE_RANK_CSV` (fallback path)
- `ENABLE_COINBASE_APP_RANK` (`true`/`false`)

## Output Files

- `output/risk_scores_full.csv`
- `output/latest_scores.csv`
- `output/feature_frames/*.csv`
- `output/category_breakdowns/{btc,total_market}.csv`
- `output/metric_breakdowns/{btc,total_market}.csv`
- `output/metric_health.csv`
- `output/source_health.csv`
- `output/sanity_report.csv`

## Phase 2 (deferred)

- Macro/recession block (yield curve, labor, DXY/VIX)
- Web frontend + scheduled cloud deployment
- Notification redesign for hosted workflow
