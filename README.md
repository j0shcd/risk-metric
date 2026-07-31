# risk-metric

A personal experiment in composing a crypto "risk score" for Bitcoin from public data, and serving it as a small dashboard that keeps itself up to date.

**Live dashboard →** https://risk-metric.pages.dev/

> This is a learning project, not a financial product. Don't make investment decisions from it.

## Why this exists

I wanted an excuse to wire together the full path from "messy public data" to "thing on the internet that updates by itself." Bitcoin made a good target: the data is open, the signals are varied (price, on-chain, macro, social), and there is no shortage of opinions on what "risk" should mean.

The interesting part wasn't picking the perfect formula — it was the end-to-end exercise:

- **Heterogeneous sources.** Pulling from CoinGecko, Binance, FRED, Wikimedia pageviews, YouTube, Reddit, and the Fear & Greed Index — each with its own auth model, rate limits, and gaps. Building a single profile-driven layer that degrades gracefully when a key is missing or a source is down.
- **Turning signals into a data model.** Normalizing time series onto a common index, scoring each metric, grouping them into categories (market, on-chain, sentiment, social, cycle), and combining them into a small set of composite indices without the result being purely arbitrary.
- **Serving it on the web.** A React + Vite dashboard reads versioned JSON artifacts produced by the Python pipeline. The contract between backend and frontend is just a folder of JSON files, which kept the two sides decoupled and easy to iterate on.
- **Keeping the data fresh.** A GitHub Action runs the pipeline daily, refreshes the cached sources, regenerates the JSON, and commits it back to the repo. Cloudflare Pages picks up the commit and redeploys. No server to babysit.

## How it fits together

```
public APIs ──► risk_engine (Python) ──► data/web/v2/*.json ──► web/ (React + Vite) ──► Cloudflare Pages
                                                ▲
                                                │
                                  GitHub Action (daily cron, 06:00 UTC)
```

- `risk_engine/` — fetch, normalize, score, and aggregate. Source modules grouped by signal family: `market`, `onchain`, `sentiment`, `social`, `cycle`.
- `publish_web.py` — pipeline entrypoint. Runs the engine and writes the JSON the frontend consumes.
- `web/` — React + Vite dashboard, Chart.js for plots. Reads only the JSON artifacts; has no knowledge of the Python side.
- `.github/workflows/daily-web-publish.yml` — the daily cron that keeps everything fresh.

## Release and alert operations

Each web publish has a `release_id`. Every JSON artifact carries that ID, and
`manifest.json` records each artifact's SHA-256 digest and byte size. The daily
workflow validates both the source and copied web release before staging it;
the alert sender refuses mixed, modified, or stale releases.
The ID is the full SHA-256 of the complete canonical artifact digests plus the
model/config identity; both backend validation and the browser reject mixed
release IDs or unexpected artifact sets.

`scripts/archive-release.mjs` appends one compact snapshot record per release
to `data/web/archive/release_snapshots.ndjson`. It deduplicates release IDs and
hard-fails before the prospective archive exceeds 250,000,000 bytes. Upload is
a no-op by default. An optional HTTP PUT boundary can be enabled with
`RELEASE_ARCHIVE_UPLOAD_URL` and, if needed, `RELEASE_ARCHIVE_UPLOAD_TOKEN`.
Each record includes the normalized feature values consumed on that run,
source/metric provenance, canonical content hashes, and model/config identity.

Alert subscriptions use hashed confirmation and unsubscribe tokens, POST-only
state changes, a 15-minute per-address confirmation cooldown, and an atomic
50-send hourly global ceiling. Alert deliveries are unique by subscriber,
release, and zone; Resend receives a deterministic idempotency key and D1 keeps
pending/sent/failed retry state for about one year. Existing D1 databases must
apply `infra/d1/migrations/0002_release_alert_safety.sql` before deploying the
new Pages functions or alert sender. Legacy plaintext tokens remain readable
only during migration and are cleared when used or rotated.

## Run it locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python publish_web.py

cd web && npm install && npm run dev
```

Without API keys the pipeline falls back to a `free_stable` profile (fewer signals, no auth required). The deployed dashboard runs the broader `extended` profile — see `.env.example` for the keys involved (FRED, YouTube, Wikimedia).

## Tests

```bash
python -m unittest discover -s tests
cd web && npm test
```

## License

MIT — see [LICENSE](LICENSE).
