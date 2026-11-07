# Fixed attention-surge candidate

Hypothesis: unusually intense public attention relative to its established level marks speculative crowding and higher Bitcoin risk. The single preregistered variant uses English Wikipedia Bitcoin page-view counts, not price, macro, or outcome labels. Its falsifier is failure of the fixed high-risk ordering and direct-CDF forecasts against the required strong reference atlas; a gain explained only by the unavailable-era partition does not support the attention mechanism. No outcome scoring has been performed by this author.

At each query, use the 395 consecutive calendar days ending query minus two days. Compare the latest 30-day arithmetic mean R against the preceding, nonoverlapping 365-day mean B. Risk is R/(R+B). Require every count finite, nonnegative, integral and at most 2**53−1 (the exact-safe integer domain), and B positive; otherwise return neutral 0.5 with an explicit status and valid-day count. Counts are scale invariant under positive integer rescaling. Parameters are fixed economic/calendar choices, not fitted values. The two-day lag is an assumed availability buffer, not verified publication timing.

The frozen input is `wikipedia_pageviews_btc.csv` from the development-only bundle ending 2022-12-31. The current source producer, `risk_engine/sources/cycle.py::_fetch_wikipedia_pageviews`, requests `en.wikipedia/all-access/all-agents/Bitcoin/daily`, copies API `views`, and does not normalize counts. All-agents counts include automated traffic; English-language article interest is not unique people, verified investor participation, or global sentiment. Original cache retrieval and revision vintages remain unverified. Source-code semantics do not prove this cache's historical provenance. No API refresh or source writes are used.

The 97 common monthly outputs contain 78 available values and 19 neutral values (December 2014–June 2016); first available is July 2016. The source itself has 2,741 nonmissing daily observations beginning July 2015, so warmup availability differs from raw-source availability. Missingness partitions eras and may confound favorable comparisons. News, controversy and distress can increase views too, contradicting the crowding direction. No correction or alternate sign will be selected from evaluation results.

Other frozen channels were inspected only for semantics/availability: YouTube is empty; fear/greed starts February 2018 and is a composite; on-chain columns are precomputed MVRV/issuance proxies with normalization/price dependencies and unverified reconstruction provenance. They are not blended into this arm.

Reproduce with the existing Python runtime:

```
python -m unittest tests.test_nonprice_a
python -m research.candidates.nonprice_a.generator --bundle /private/tmp/risk-hillclimb-inputs-gj866s2j --output /private/tmp/NEW-exclusive-output.csv
```

The manifest freezes parameters, source/producer/prediction hashes and availability. Synthetic tests cover independent lag/window arithmetic, prefixes, poisoned future values, missing/invalid domains, zero baselines and scale invariance. Deliberately removing the lag, filling gaps from the final observation, and accepting negative counts each made the tests fail; source restored afterward. A later independent review found overflow for accepted 1e308 counts; the explicit exact-safe integer bound now neutralizes such history. Its regression fails when the bound is removed; all 97 real-input output rows remain byte-identical. The real-input CLI produced finite values on all 97 dates without evaluating outcomes. Next step: independent source review, then root submits exactly one frozen slot to the shared development campaign. No production or external-equity change is proposed.
