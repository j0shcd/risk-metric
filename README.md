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

## Release operations

CI and daily publishing use a checksum-verified official Node 22.23.4 archive
in an isolated runner directory. The shared local action checks its version
and prepends its bin directory through `GITHUB_PATH`, preserving the configured
Python interpreter. Daily publishing sets up Node before syncing or validating
release artifacts. Shell regressions in `tests/test_workflow_node_setup.py`
cover runtime shadowing, checksum failure, version mismatch and setup ordering.

Each web publish has a `release_id`. Every JSON artifact carries that ID, and
`manifest.json` records each artifact's SHA-256 digest and byte size. The daily
workflow validates both the source and copied web release before staging it.
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

## Public JSON

- [Today](https://risk-metric.pages.dev/api/v1/latest.json): date, reading, region,
  four `sub_scores`, availability status, and release identity.
- [History](https://risk-metric.pages.dev/api/v1/history.json): dated rows of the
  reading and four sub-scores, with column names in `fields`.

Values run from 0 to 100, rounded to one decimal. Sub-scores are
`looks_like_past_peaks`, `unlike_past_bottoms`, `price_stretch`, and
`speculation_and_hype`. These are the same contributions shown on Today;
low component coverage or a missing current reading makes Today unavailable
and sets the latest JSON values to null. History includes only finite readings.
Version 1 is stable: fields only get added, never renamed. There is no key,
server code, or user data. Users bring their own rules; the numbers are not
validated buy or sell signals.

The daily workflow commits refreshed release artifacts. Cloudflare Pages runs
`npm run build` in `web`: `prepare:web` syncs that release, then
`scripts/build-public-api.mjs` generates `public/api/v1/*.json` before Vite
copies it into the site. Generated API files follow the tracked `public/data`
convention; Pages always regenerates them from the current release.
`public/_headers` enables public cross-origin reads and one-hour caching.

## Run it locally

Use a patched runtime: the project pins Python 3.11.18 and Node 22.23.4.
See [security maintenance](docs/security.md) for the audit, remaining upstream
risks, monitoring activation, and dependency-update procedure.

```bash
bash scripts/security-check.sh
python -m venv .venv && source .venv/bin/activate
pip install --require-hashes --only-binary=:all: -r requirements.txt
python publish_web.py

cd web && npm run reinstall && npm run dev
```

Without API keys the pipeline falls back to a `free_stable` profile (fewer signals, no auth required). The deployed dashboard runs the broader `extended` profile — see `.env.example` for the keys involved (FRED, YouTube, Wikimedia).

## Tests

The [indicator benchmark plan](docs/metric_evaluation_plan.md) owns the implemented
retrospective information scorecard, its trust limits and next bounded work.
[DCA evidence](docs/dca_evidence.md) records the current historical results.
The scorecard compares common dates, return/downside endpoints and forecast loss
without a combined winner. Its automatic search failed qualification; it must not
be used for automatic promotion. A portable snapshot and offline replay command
are in the plan. The existing acceptance gate remains unchanged.

CI prepares the ignored `config/runtime.json` from the credential-free
`config/model_acceptance_runtime.json` before testing. This fixture reproduces
the frozen canonical model/configuration hashes. Preserve its bytes when moving
it; changing it is a model change. In a fresh checkout, initialize it only when
no local runtime override exists:

```bash
test -e config/runtime.json || cp config/model_acceptance_runtime.json config/runtime.json
python -m unittest discover -s tests
cd web && npm test
```

## License

MIT — see [LICENSE](LICENSE).
