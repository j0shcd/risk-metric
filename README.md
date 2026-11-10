# risk-metric

A small research programme studying whether public data can improve our understanding of Bitcoin's future returns and losses. We keep the benchmark fixed, test a few clearly recorded ideas at a time, and retain failures as well as successes.

**Live dashboard →** https://risk-metric.pages.dev/

> No indicator has yet demonstrated dependable improvement across our comparisons. The dashboard is an experimental display, not a validated trading signal.

## Research first

The aim is gradual, measurable improvement rather than one promising backtest.
Every candidate faces the same dates and outcomes, with information limited to
what its declared historical reconstruction allows. We compare returns and losses
separately; a change in investment size or contribution schedule cannot improve
the information score. Historical data revisions and repeated inspection of the
same market periods limit what these results establish.

Start with the [research record](docs/metric_evaluation_plan.md). Its opening
sections explain the current approaches, what worked, what failed and the active
round. The same document owns the frozen benchmark, reproducible evidence,
attempt history, data limitations and next steps. Legacy strategy-specific
experiments remain in [DCA evidence](docs/dca_evidence.md).

Two November 7 rounds tested six new ideas: unusual market states, a small
learner, an ensemble, sign persistence, recovery after a fall and changing
volatility. None beat the strongest reference on the declared two-year return
comparison. They remain reproducible negative evidence, with no model promotion.
The macro audit found backfilled/revised history and unresolved source-use and
original-version questions; no newly captured macro values entered round two.
A third round used independently checked Federal Reserve Board releases,
explicitly reconstructed rather than authenticated historical vintages.
Its three new ideas also failed the primary comparison. A registered artificial
market audit then found useful input information without improved two-year
forecasts from the current readout. Its uncertainty intervals were much too
narrow. The November 10 six-month target/readout study provides usable continuous
training labels, but none of its seven new forecasters beats Fixed DCA at the
historical median and uncertainty remains poorly calibrated. Feature searches
remain paused; the next proposed work concerns scale calibration and an explicit
decision objective. The original market benchmark and historical verdicts stay
fixed. The research record contains results and portable replay packets.
Separately, six baseline forecasts were archived before their starting point;
none has a mature outcome yet. The next registered monthly observation is
November 30, 2026.

## Existing dashboard

The original dashboard combines market, on-chain, macro and attention inputs.
Track record now lets visitors choose among 96 historical four-year periods and
set a monthly USD contribution to compare regular buying with score-based buying.
Both strategies receive identical cashflows and spend the full budget by the end,
including purchase costs. The comparison scales frozen November evidence; it
does not fetch live prices or run a new model. Experimental alternatives and
their limitations are available in the same view.

Python produces versioned JSON for the market dashboard and React displays it. Its scheduled refresh must
refuse an engine/model identity that differs from the accepted production model,
before fetching data or publishing. Research commits can therefore be published
without silently promoting an experimental model. The legacy model-acceptance
gate and canonical identity remain unchanged. Research CI checks correctness and
security; production performance evaluation runs in the explicit
`model-acceptance.yml` workflow. Current engine revisions are unaccepted, so the
scheduled dashboard refresh is held and existing published artifacts remain.
See [ADR 0009](docs/adr/0009-separate-research-ci-from-production-promotion.md).

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
a no-op by default. An optional HTTPS PUT boundary requires both
`RELEASE_ARCHIVE_UPLOAD_URL` and `RELEASE_ARCHIVE_UPLOAD_ALLOWED_ORIGIN`
(for example `https://archive.example`), plus `RELEASE_ARCHIVE_UPLOAD_TOKEN`
if authentication is needed. The URL must match that exact approved origin;
redirects are rejected, the upload has a 30-second deadline, and the input
must be a regular file within the archive byte budget. A configured URL without
an approved origin fails closed; no upload setting is changed automatically.
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
without a combined winner. A finite known-law synthetic panel test now passes;
market automatic promotion remains unqualified. A portable snapshot and offline replay command
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
