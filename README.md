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
- source mode provenance checks (API vs fallback cache vs unavailable)
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
  - BTC price-structure fallback proxies are only enabled when total-market coverage is insufficient
  - Local `total_marketcap.csv` is maintained over time (historical APIs when available, otherwise daily free global snapshot append)
- On-chain:
  - MVRV Z-score
  - Puell Multiple
  - Supply in profit / implied loss
- Sentiment/social:
  - Fear & Greed index
  - YouTube activity basket
  - Google Trends (official API adapter when configured, fallback local history CSV otherwise)
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
- Reliability is further adjusted by adapter provenance (`api` > `fallback cache` > `snapshot fallback` > `unavailable`).

## Running

### 0) Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

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
python backfill.py --target total-market
```

### 4) Refresh social local stores only

```bash
python backfill.py --target social
```

### 5) Refresh on-chain local store only

```bash
python backfill.py --target onchain
```

### 6) Validate output health

```bash
python validate.py
```

### 7) Publish web contract artifacts (single-run orchestration)

Runs pipeline once, validates once, writes CSV outputs, and exports web JSON artifacts to `data/web/v1`.

```bash
python publish_web_v1.py
```

Validation warnings do not block export. Hard validation failures return non-zero and block export.

### 8) Run frontend dashboard locally

```bash
cd web
npm install
npm run dev
```

`npm run build` automatically syncs canonical artifacts from `data/web/v1` into `web/public/data/v1`.

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
- `GOOGLE_TRENDS_API_KEY` (optional)
- `GOOGLE_TRENDS_API_URL` (optional; required for live Google Trends fetch)
- `GOOGLE_TRENDS_TERMS` (comma-separated; default: `bitcoin`)
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
  - includes `source_mode`, `reliability_mode_multiplier`, and `adjusted_base_reliability`
- `output/source_health.csv`
- `output/source_modes.csv`
- `output/sanity_report.csv`

## Web Contract (`data/web/v1`)

Canonical web artifacts are versioned under `data/web/v1`:

- `manifest.json`
- `latest_snapshot.json`
- `history_core.json`
- `category_breakdowns_btc.json`
- `category_breakdowns_total_market.json`
- `metric_breakdowns_btc.json`
- `metric_breakdowns_total_market.json`
- `diagnostics.json`

Contract guarantees:

- Stable score and confidence keys.
- Stable ISO date/timestamp formats.
- Explicit degraded-source metadata (mode + availability/staleness) is exported, never inferred.
- Additive-only changes within `v1`; breaking changes require `v2`.

## Cloud Deployment (Cloudflare Pages + GitHub Actions)

Scheduled publishing is configured in `.github/workflows/daily-web-publish.yml` and runs daily at `06:00 UTC`.

Behavior:

- Executes `python publish_web_v1.py`.
- Fails fast and does not commit when validation hard-fails.
- Commits updated `data/web/v1` artifacts to `main` only when diffs exist.
- Cloudflare Pages redeploys automatically from `main`.

### One-Time Cloudflare Pages Setup

1. In Cloudflare Pages, connect this GitHub repository.
2. Set production branch to `main`.
3. Set root directory to `web`.
4. Set build command to `npm run build`.
5. Set output directory to `dist`.
6. Confirm deployments are public and use the free tier defaults.
7. Trigger first deploy manually once, then rely on commits from the scheduled workflow.

## Phase 2 (deferred)

- Macro/recession block (yield curve, labor, DXY/VIX)
- Notification redesign for hosted workflow
