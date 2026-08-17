# DCA Risk Evidence

Status: three-test design implemented  
Reference data window: 2014-12-31 through 2026-07-31  
Last evaluated: 2026-08-01

## What is being tested

The suite separates three questions that the previous combined strategy test could not distinguish:

1. Does DCA Risk improve accumulation when selling is prohibited?
2. Does DCA Risk add value when de-risking an existing BTC position?
3. Does the score itself identify better and worse forward-looking regions, independent of a trading policy?

The tests are diagnostics of the existing frozen score and default 0.25/0.75 policy regions. They were designed after historical data had already been observed and must not be described as prospective proof.

## Common rules

- Every decision uses the prior month's score. The monthly close cannot trade on itself.
- Results are evaluated from every monthly start date leaving at least 48 months, not one selected start.
- DCA Risk is compared with a causal price-only risk score. The comparator ranks log price relative to its trailing 48-month median using expanding history only; it has no future normalization.
- Trades pay the configured 0.20% fee and slippage.
- Idle cash earns a declared 3% annual yield.
- Future-suffix mutation tests must leave all earlier scores, trades, and ledger states unchanged.

A stop-loss is intentionally outside the compact core: it answers a short-horizon loss-control question rather than whether broad valuation regions are informative. It can remain an exploratory benchmark without becoming another headline test.

## Test 1: accumulation only

Every strategy receives the same monthly contribution. Selling is prohibited.

- `fixed_dca` invests each contribution immediately.
- `risk_accumulation` accelerates purchases in the frozen low-risk region.
- `price_only_accumulation` applies the identical purchase mechanics to the causal price-only score.
- Deferred contributions must begin forced deployment after 48 months, matching the declared cycle-scale horizon and preventing permanent cash from masquerading as risk control.

Primary evidence across 93 rolling starts:

- DCA Risk accumulation beat Fixed DCA in 26.88% of windows.
- Median terminal wealth was 21.46% below Fixed DCA.
- It did outperform the price-only accumulation rule by 2.97 contribution-denominated wealth units at the median.

Verdict: not supported versus Fixed DCA. The score was better than this particular price-only timing rule, but deferral still imposed more opportunity cost than it recovered.

## Test 2: de-risking

Every strategy starts with exactly one BTC and no later contributions. This removes the early-funding and contribution-timing confound.

- `hold` never trades.
- `risk_derisking` sells progressively in the frozen high-risk region and redeploys progressively in the low-risk region.
- `price_only_derisking` uses the identical trade mechanics with the causal price-only score.

Primary evidence across 93 rolling starts:

- DCA Risk finished above hold in 68.82% of windows.
- It had a higher Calmar-like return/drawdown ratio in 90.32% of windows.
- Median maximum-drawdown reduction versus hold was 24.18 percentage points.
- Median Calmar improvement versus hold was 0.403 and versus the price-only policy was 0.457.

Cashflow-policy attribution adds the requested exit-only strategy under identical contributions:

| Strategy | Median wealth delta vs Fixed DCA | Win rate vs Fixed DCA |
| --- | ---: | ---: |
| Risk-varying buys only | -21.46% | 26.88% |
| Fixed monthly buys + risk-based sells | -9.23% | 5.38% |
| Risk-varying buys + risk-based sells | -26.01% | 26.88% |

This is an important split: risk-based selling helped an investor who already held one BTC, but did not beat Fixed DCA when layered onto an ongoing contribution plan. Exit timing appears more valuable than purchase timing, yet its value depends strongly on the investor's starting exposure and cashflow problem.

Verdict: historically promising for de-risking. This is the strongest evidence currently available, but it is reconstructed rather than prospective and the default thresholds were created with knowledge of Bitcoin history.

## Test 3: policy-independent signal value

Each observation is assigned to the frozen low (`≤0.25`), mid, or high (`≥0.75`) region. The test measures subsequent 48-month return, maximum drawdown, and maximum rally without simulating trades. Circularly shifted score histories provide timing placebos.

| Signal | Horizon | Low minus high return | Low minus high drawdown | Return placebo p |
| --- | ---: | ---: | ---: | ---: |
| DCA Risk | 48m | -938.61% | -0.57 pp | 0.881 |
| Price-only risk | 48m | +163.90% | +46.22 pp | 0.390 |

Positive values are directionally useful: low-risk regions later returned more, while high-risk regions later suffered worse drawdowns. DCA Risk has the wrong ordering over 48 months and is not unusual relative to its timing placebos. The simple causal price-only score has the expected ordering, but it also fails the timing-placebo threshold.

Only 92 overlapping DCA Risk observations remain, equivalent to roughly one non-overlapping 48-month observation after the conservative overlap adjustment. Bitcoin's available history therefore cannot provide a well-powered, independent four-year statistical test. The large percentages should not be read as precise effect estimates.

Verdict: not supported as an independently reliable region-ranking signal.

## Interpretation

The revised evidence is not equivalent to “never sell is best.” It says:

- DCA Risk has not earned its opportunity cost as an accumulation-timing tool.
- The default DCA Risk regions produced a strong historical de-risk/re-entry policy relative to hold and the chosen price-only rule.
- That de-risking result is not corroborated by the policy-independent four-year region test, so it should be treated as promising but vulnerable to policy/path dependence and researcher degrees of freedom.

The appropriate product claim remains conservative until prospective releases accumulate. The three artifacts should be read together rather than promoting the one favorable result in isolation.

## Why realized cap is not the primary “average investor” benchmark

Realized cap values each UTXO at the price when it last moved; realized price divides that aggregate value by supply. It is reasonably described as a proxy for aggregate network cost basis, but not as a ledger of the average person's deposits, emotions, taxes, or realized return. See the [Coin Metrics definition](https://docs.coinmetrics.io/asset-metrics/market/capact1yrusd) and [Glassnode methodology](https://docs.glassnode.com/guides-and-tutorials/metric-guides/realized-capitalization).

It is also not independent here: DCA Risk already includes an MVRV-derived component, and MVRV uses realized cap. Benchmarking the composite against a realized-cap strategy would partly compare the model with one of its own inputs. The current reproducible store contains a causal MVRV z-score proxy, not raw realized cap or realized price.

Realized price may still be useful later as a clearly labeled behavioral anchor—for example, “did the strategy acquire below aggregate network cost basis more often?”—but it should not be promoted as an independent average-investor return benchmark without a separately versioned raw series.

## Regression and leakage protection

The evaluator and unit tests assert that:

- full and rolling accumulation ledgers receive identical external cashflows;
- accumulation policies never sell;
- de-risking policies start with the same one-BTC position and receive no contributions;
- executions use the prior month's DCA Risk value;
- mutating all future DCA Risk values cannot alter earlier accumulation or de-risking states;
- mutating future prices cannot alter the earlier causal price-only score;
- DCA Risk construction itself is prefix-invariant to future component mutations.

Any causality-audit failure blocks DCA evidence claims.

The automated model-acceptance gate uses equal-cashflow accumulation wealth versus
Fixed DCA as its primary improvement target. Exit-only wealth, one-BTC de-risking
Calmar, and 48-month region ordering are non-inferiority guardrails; causality and
source availability must remain true, and a dedicated gate prevents the signal
horizon from silently reverting below 48 months. The former registered 6/12-month
DCA AUC hypotheses are now exploratory and cannot promote a model.

## Reproduce

```bash
python evaluate_metrics.py run-artifacts \
  --profile standard \
  --artifact-dir output \
  --run-id dca-evidence-three-tests
```

The main artifacts are:

- `tables/dca_evidence_summary.csv`
- `tables/dca_accumulation_windows.csv`
- `tables/dca_derisking_windows.csv`
- `tables/dca_policy_attribution_windows.csv`
- `tables/dca_signal_value.csv`
- `tables/dca_causality_audit.csv`
