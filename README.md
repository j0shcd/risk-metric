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

### 3) Validate output health

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
- `GOOGLE_TRENDS_CSV` (fallback path)
- `COINBASE_RANK_CSV` (fallback path)
- `ENABLE_COINBASE_APP_RANK` (`true`/`false`)

## Output Files

- `output/risk_scores_full.csv`
- `output/latest_scores.csv`
- `output/feature_frames/*.csv`

## Phase 2 (deferred)

- Macro/recession block (yield curve, labor, DXY/VIX)
- Web frontend + scheduled cloud deployment
- Notification redesign for hosted workflow
