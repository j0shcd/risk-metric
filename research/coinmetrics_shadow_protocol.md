# Coin Metrics paper witness adapter v1

Implemented and tested offline only. No provider-price acquisition, forecast issue,
cohort registration, or performance measurement has occurred in this implementation.
Root owns source review, registration and approval of one subsequent capture.
The operational 2026-11-07 witness and formal 2026-11-30 monthly cohort must have
separate immutable registrations. A missed date is never relabeled as current.

`coinmetrics_shadow.produce((owned_raw_bytes,), CONFIG, query_day)` is the pure
producer. `fetch({'query_day': 'YYYY-MM-DD'})` is the explicitly networked callback
for `shadow_capture.capture_response`. Registration binds `CODE_PATHS`, CONFIG
(the exact companion JSON), the v3 boundary and runtime. No invocation on import.
No scheduler, CLI acquisition shortcut, account, credential or trading action.

## Frozen source and transport

Only `https://community-api.coinmetrics.io/v4/timeseries/asset-metrics` is allowed:
assets=btc, metrics=PriceUSD, frequency=1d, start_time=2017-01-01T00:00:00Z,
end_time=query-day00:00UTC, end_inclusive=false, page_size=10000,
paging_from=start, format=json. Pagination may add only next_page_token and must
preserve the fixed host, path and parameters. No redirects, proxy environment,
authentication, cookies, compression, fallback or source stitching.

At most six requests including retries, two seconds between starts, ten-second
per-operation timeout, internal 50-second budget and an owned subprocess killed
and reaped at 55 seconds. The subprocess uses a fixed module, no shell and a
sanitized environment. Each response is limited to 2 MiB; aggregate returned body
bytes are limited to 5 MiB and rows to 10,000. Base64 envelopes therefore fit the
capture boundary's 8 MiB cap. Every obtained chunk is checkpointed before parsing;
failed/partial captures retain evidence through typed CaptureFailure and cannot
produce forecasts. The collector examines pagination and row count, never prices.
Raw API bodies remain exact bytes inside the envelope; retries are retained too.

## Calendar, price and availability

PriceUSD is a **provider reference close**, not an executable venue price. The
provider's daily bar timestamp D labels the interval beginning D; its selected
close instant is D+1 at 00:00 UTC. Future/open rows are excluded by timestamp
before reading price values. Selected rows must have the exact asset/metric,
finite positive prices and every consecutive daily close from 2017-01-02 through
the query day's 00:00 UTC. No interpolation, duplicate or missing close is allowed.
A stale current close fails the adapter's quality gate; this is separate from the
archive's general causal eligibility of older information.

The compact selected prefix declares first_close_at, step_seconds=86400 and the
ordered prices. It reconstructs every selected Date without using bar-start dates.
It is capped at 128 KiB. Current captures establish **observed by retrieval**, not
first publication or historical point-in-time correctness. Revision captures are
new immutable objects; replay uses the original capture. No published_at is made up.

The provider FAQ describes a 61-minute reference-rate calculation window. The
cohort and CONFIG pin entry_observation_buffer_seconds=7200: content publication
must finish strictly before next UTC entry minus two hours. This conservative
operational deadline does not assert the exact calculation-window start or first
publication time and does not change entry or outcome labels.

## Three frozen baselines, six forecasts

Only terminal log returns at 12 and 24 calendar months. Virtual entry is the next
UTC day's close instant, end is entry plus the calendar horizon, and label
availability is end plus one UTC day. Each empirical distribution uses the latest
24 monthly-origin labels with availability **strictly before** query day. Context
is log-price change over 12 calendar months and sample volatility (ddof=1) of the
last 90 daily log returns. Median bins are fitted to that same 24-label feature
pool; context uses the existing 50% pooled / 50% matching-cell mixture with pooled
fallback when the cell is empty. Missing BTC components remain None, never zeros.
Operational non-month-end query context is computed directly on its exact date.

The unchanged Student-t5 volatility baseline fits exactly the last 730 daily log
returns, simulates 8192 joint paths once across both exact integer holding-day
horizons, and excludes its first next-day-entry shock from holding returns.
Seed is the big-endian integer from the first eight SHA256 bytes of
`20261107:YYYY-MM-DD`. Numerical FitError is visible; no replacement forecast.
Approximate-posterior diagnostics are retained as finite numeric features.
Empirical forecasts are `issued_cdf`; generative draws are
`iid_predictive_law_draws`. These interpretations must remain distinct when scored.
No indicator qualified for promotion, no time-control rescue, no calibration or
trading-performance claim follows from this operational infrastructure witness.

## Provider evidence and rights scope

Official documentation checked 2026-11-07:

- [API conventions and community host](https://docs.coinmetrics.io/api-reference/api-conventions)
- [PriceUSD definition](https://docs.coinmetrics.io/network-data/network-data-overview/market/price)
- [Timestamp and reference-rate FAQ](https://docs.coinmetrics.io/service-and-support/faqs)
- [Community package and Creative Commons link](https://docs.coinmetrics.io/packages/coin-metrics-community-data)
- [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)

The authorized metadata-only catalog response retrieved at
2026-11-07T02:24:44.696638Z from
`https://community-api.coinmetrics.io/v4/catalog-v2/asset-metrics?assets=btc&metrics=PriceUSD`
reported btc/PriceUSD/1d, community=true, minimum 2010-07-18 and maximum
2026-11-06 bar-start timestamps. That establishes present metadata entitlement,
not a guarantee of complete/final future responses. The separate official GitHub
CSV was stale (May 2026) and is not used. No provider prices are redistributed here.

Scope is local noncommercial PAPER infrastructure research only. Free no-key API
access is not a claim of unrestricted redistribution rights. Commercial,
professional, publication and trading rights remain unestablished. Requests reveal
IP address to the provider; they send no account secrets or personal data. Exit
format is immutable JSON envelopes containing exact response bytes plus local
hash-bound receipts; no provider account or hosted service state is required.

## Offline checks and next step

Run `python -m unittest tests.test_coinmetrics_shadow tests.test_shadow_capture_v3`.
The collector tests use fake HTTP responses and clocks. The producer test uses
invented daily prices and the actual frozen fit/simulator, with networking and
subprocess calls forbidden. Independent context, atom, median-cell weight and
quadratic CRPS calculations check numerical meaning. Failure receipts, byte/rate/
deadline limits, future poisoning, daily gaps, physical values, strict maturity,
leap calendars and fixed configuration are covered. Deliberately reintroduced
future-value access, bar-start dates, inclusive maturity, seventh request,
cross-host access and dropped partial-failure type each fail their regression.

Next bounded step: root reviews committed code/config and registers the distinct
paper cohort against v3's pinned source closure before authorizing one current
capture. No current-market fit or acquisition is authorized by these files.
