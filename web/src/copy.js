export const METRIC_COPY = {
  trend_composite_score: {
    shortName: "Trend Composite",
    oneLiner: "A broad background composite across structure, sentiment, and on-chain signals.",
    description:
      "Trend Composite is a broad 0–100 blend of structural, on-chain, and sentiment signals. It is useful as regime context, but it is intentionally less specific than the top and bottom reversal models. Use it as a backdrop signal rather than a standalone decision trigger.",
    notMeaning:
      "Trend Composite does not directly estimate top or bottom reversal probability.",
    technicalRows: [
      { label: "Inputs", value: "Price structure, on-chain, fear/greed, social, total market context" },
      { label: "Formula", value: "Confidence-weighted blend of BTC signal (70%) and total market signal (30%)" },
      { label: "Role", value: "Context index; reversal probabilities are modeled separately" },
    ],
  },
  cycle_extension: {
    shortName: "Price stretch",
    oneLiner: "How far above its own long-run averages the price is sitting.",
    description:
      "Built from three moving-average relationships and the past year's return. Each input is ranked against its full prior history, so 100 means today is the most stretched reading ever seen. The four ranks are blended with fixed weights.",
    notMeaning:
      "a reversal model on its own. Read it next to the peaks and bottoms scores.",
    technicalRows: [
      {
        label: "Inputs",
        value: "50d/350d MA ratio, price/200d MA, price/200w MA, and 1-year return",
      },
      {
        label: "Per-input transform",
        value: "Expanding-history percentile rank using data available up to time t",
      },
      {
        label: "Weights",
        value: "0.30 (50d/350d) + 0.20 (price/200d) + 0.35 (price/200w) + 0.15 (1y ROI)",
      },
      { label: "Output range", value: "Bounded 0-1 (higher = more historically stretched)" },
      { label: "Assumptions", value: "Long-run moving averages are meaningful anchors across the full BTC price history" },
    ],
  },
  top_reversal_risk: {
    shortName: "Looks like past peaks",
    oneLiner: "How much today resembles the run-ups into past cycle peaks.",
    description:
      "Past cycle peaks are marked out after the fact, using only returns that had already resolved at the time. This score measures how closely today's valuation, speculation, attention and macro readings line up with the months that preceded those peaks. It is a similarity score, not a probability.",
    notMeaning:
      "a sell signal. Readings can stay high for many months before anything happens.",
    technicalRows: [
      { label: "Base input", value: "p_frenzy (cycle-model logistic on upper-cycle scores) + cycle structural features" },
      {
        label: "Labels",
        value: "Lower-tail 36/48-month forward returns observed from 24-month highs; outcome cuts use only already-resolved history",
      },
      {
        label: "Calibration",
        value: "Walk-forward-style alignment against prior segments; Phase 2 evidence currently blocks promoted live-style and leakage-sensitive claims",
      },
      {
        label: "Objective",
        value: "Weighted blend of lead-recall at a fixed alert rate, PR-AUC, and drawdown-avoidance KPIs",
      },
      { label: "Output range", value: "Bounded 0-1 (higher = stronger historical top-reversal alignment)" },
    ],
  },
  bottom_reversal_risk: {
    shortName: "Looks like past bottoms",
    oneLiner: "How much today resembles the stretches around past cycle bottoms.",
    description:
      "The same method as the peaks score, pointed the other way: how closely today lines up with the months that preceded past recoveries. Also a similarity score, not a probability.",
    notMeaning:
      "a buy signal, and it does not mark the low. These stretches can last a year or more.",
    technicalRows: [
      { label: "Base input", value: "p_accumulation (cycle-model logistic on lower-cycle scores) + cycle structural features" },
      {
        label: "Labels",
        value: "Upper-tail 36/48-month forward returns observed from 24-month lows; outcome cuts use only already-resolved history",
      },
      {
        label: "Calibration",
        value: "Walk-forward-style alignment against prior segments; Phase 2 evidence currently blocks promoted live-style and leakage-sensitive claims",
      },
      {
        label: "Objective",
        value: "Weighted blend of lead-recall at a fixed alert rate, PR-AUC, and recovery-capture KPIs",
      },
      { label: "Output range", value: "Bounded 0-1 (higher = stronger historical bottom-reversal alignment)" },
    ],
  },
  headline_attention: {
    shortName: "Signals agreeing",
    oneLiner: "How many of the inputs are saying the same thing right now.",
    description:
      "High when many inputs are at historical extremes and pointing the same way. Low when they are mixed or quiet. It says how loud the evidence is, not which direction it points.",
    notMeaning:
      "directional. A high reading happens in panics and in manias alike.",
    technicalRows: [
      { label: "Inputs", value: "Price structure, on-chain, fear/greed, social, total market context" },
      {
        label: "Per-metric attention",
        value: "Each metric reports its own 0-1 'attention' (high when its current reading is in a historical extreme tail)",
      },
      {
        label: "Per-category aggregation",
        value: "Reliability-weighted mean of available metrics in each category",
      },
      {
        label: "Sign-consensus boost",
        value: "category attention × (1 + 0.20 × sign-consensus), capped at 1.25 (more inputs agreeing direction → louder)",
      },
      {
        label: "Disagreement boost",
        value: "× (1 + 0.15 × normalized cross-metric stdev), capped at 1.15 (high dispersion still counts as 'urgent')",
      },
      {
        label: "Headline blend",
        value: "0.70 × BTC-scope attention + 0.30 × total-market-scope attention, then clipped to [0, 1]",
      },
    ],
  },
  cycle_regime: {
    shortName: "Speculation and hype",
    oneLiner: "How much froth is showing up in valuation, volume and attention.",
    description:
      "A monthly blend of four percentile readings: valuation, speculation, attention, and macro conditions. Higher means more of the froth that showed up near past peaks.",
    notMeaning:
      "a timing tool. It describes conditions; it says nothing about how long they last.",
    technicalRows: [
      {
        label: "cycle_frenzy_score",
        value: "Monthly weighted blend of upper-cycle valuation, speculation, attention, and macro percentiles",
      },
      {
        label: "cycle_accumulation_score",
        value: "Same construction on the lower-cycle side; uses the same category weights",
      },
      {
        label: "p_frenzy / p_accumulation",
        value: "Logistic mapping, then shrunk toward 0.5 using confidence = mean(category coverage, raw-feature coverage)",
      },
      { label: "Output", value: "Confidence-adjusted frenzy probability; bounded 0-1" },
      { label: "Assumption", value: "Historical valuation/speculation extremes remain informative about current regime" },
    ],
  },

  btc_drawdown_from_ath: {
    shortName: "Drawdown from ATH",
    oneLiner: "How far BTC price is from its most recent all-time high.",
    description:
      "Raw percentage decline of BTC close from its running cumulative-max (all-time high). The raw value is non-positive (0 at a new ATH; -0.8 at 80% below ATH). Higher signal in this dashboard means a small drawdown (near ATH); lower signal means a deep drawdown.",
    technicalRows: [
      { label: "Raw formula", value: "(BTC close / cummax(BTC close)) - 1, in [-1, 0]" },
      {
        label: "Normalization",
        value: "Rolling robust z-score blended with expanding-history percentile, then mapped to a signed signal in [-1, 1]",
      },
      { label: "Sign convention", value: "+ = near ATH, - = deep drawdown" },
      { label: "Scope", value: "BTC price only" },
    ],
  },
  btc_trend_extension: {
    shortName: "Trend Extension (50d/350d)",
    oneLiner: "How extended BTC is relative to its long-run moving average.",
    description:
      "Ratio of BTC's 50-day moving average to its 350-day moving average. Values >1 mean the short-term average is above the long-term trend (historically associated with overextension); values <1 mean the short-term is below trend. The raw ratio is normalized into a signed signal channel for plotting and scoring.",
    technicalRows: [
      { label: "BTC raw formula", value: "SMA_50(BTC close) / SMA_350(BTC close)" },
      {
        label: "Total-market raw formula",
        value: "SMA_50(total market cap) / SMA_350(total market cap)",
      },
      {
        label: "Normalization",
        value: "Rolling robust z-score blended with expanding-history percentile → signed signal in [-1, 1]",
      },
      { label: "Sign convention", value: "+ = extended (50d above 350d), - = below trend" },
    ],
  },
  btc_log_reg_deviation: {
    shortName: "Log Regression Deviation",
    oneLiner: "How far BTC price deviates from its long-run logarithmic trend.",
    description:
      "Bitcoin's price on a log scale has historically followed a decelerating growth trend. This metric measures how far current price sits above or below a log-linear regression fit (in log time, log price) over all available history. Above the trend line → positive raw residual; below → negative.",
    technicalRows: [
      {
        label: "BTC raw formula",
        value: "BTC close / exp(polyfit(log(time), log(BTC close))) — fit refit each day on history up to t",
      },
      { label: "Total market", value: "Same formula applied to total market cap" },
      {
        label: "Normalization",
        value: "Rolling robust z-score blended with expanding-history percentile → signed signal in [-1, 1]",
      },
      { label: "Assumption", value: "BTC roughly follows a power-law / log-linear long-run trend across cycles" },
    ],
  },
  btc_realized_vol: {
    shortName: "Realized Volatility (30d)",
    oneLiner: "How volatile BTC has been over the past 30 days.",
    description:
      "Annualized standard deviation of BTC's daily log returns over a rolling 30-day window. The signal direction is inverted in this dashboard: high realized volatility maps to low signal, low realized volatility maps to high signal. Extended quiet periods have historically sometimes preceded larger directional moves.",
    technicalRows: [
      { label: "Raw formula", value: "std(daily log returns over last 30 days) × sqrt(365)" },
      {
        label: "Normalization",
        value: "Rolling robust z-score blended with expanding-history percentile → signed signal in [-1, 1]",
      },
      { label: "Sign convention", value: "Inverted: high realized vol → low signal" },
      { label: "Scope", value: "BTC only" },
    ],
  },
  mvrv_ratio_z_proxy: {
    shortName: "MVRV Ratio Z Proxy",
    oneLiner: "An expanding standardization of CoinMetrics' market-value/realized-value ratio.",
    description:
      "Uses CoinMetrics' market-cap-to-realized-cap ratio and standardizes that ratio against its expanding historical mean and standard deviation. It is a proxy channel, not the canonical MVRV Z-Score formula based on the market-cap minus realized-cap spread.",
    technicalRows: [
      {
        label: "Raw formula",
        value: "(MVRV ratio - expanding mean) / expanding standard deviation, after 365 observations",
      },
      {
        label: "Normalization",
        value: "Rolling robust z-score blended with expanding-history percentile → signed signal in [-1, 1]",
      },
      { label: "Sign convention", value: "+ = market priced well above on-chain cost basis" },
      { label: "Scope", value: "BTC on-chain data" },
    ],
  },
  mvrv_implied_profitability_proxy: {
    shortName: "MVRV-implied Profitability View",
    oneLiner: "A display-only transformation of the same MVRV ratio source.",
    description:
      "This bounded view makes the MVRV ratio easier to read as a rough profitability context. It is not measured supply in profit, is not an independent on-chain observation, and has zero separate weight in the scoring model.",
    technicalRows: [
      { label: "Source", value: "Derived from the same CoinMetrics MVRV ratio used by the MVRV Ratio Z Proxy" },
      { label: "Role", value: "Display only — excluded from scoring and evidence counts" },
      { label: "Interpretation", value: "Higher values imply more aggregate unrealized profitability; they do not estimate literal supply in profit" },
    ],
  },
  fear_greed: {
    shortName: "Fear & Greed Index",
    oneLiner: "Composite crowd sentiment from alternative.me.",
    description:
      "A widely-followed composite sentiment indicator for Bitcoin, published daily by alternative.me. The raw score combines price momentum, volatility, market volume, social media activity, and Google Trends data into a 0-100 reading (0 = extreme fear, 100 = extreme greed). Here it is normalized into a signed signal channel.",
    technicalRows: [
      { label: "Source", value: "alternative.me (public API), daily 0-100 score" },
      {
        label: "Normalization",
        value: "Rolling robust z-score blended with expanding-history percentile → signed signal in [-1, 1]",
      },
      { label: "Sign convention", value: "+ = greed/euphoria, - = fear" },
    ],
  },
  btc_dominance: {
    shortName: "BTC Dominance",
    oneLiner: "BTC's relative strength within the total crypto market.",
    description:
      "Proxy for BTC's relative strength within the broader crypto market. Each side is normalized by its own all-time high so the ratio is unitless. High readings mean BTC is closer to its own peak than the total market is to its peak (BTC outperforming); low readings mean the total market is outperforming BTC (typical of altcoin-heavy rallies).",
    technicalRows: [
      {
        label: "Raw formula",
        value: "(BTC close / max(BTC close)) / (total market cap / max(total market cap))",
      },
      {
        label: "Normalization",
        value: "Rolling robust z-score blended with expanding-history percentile → signed signal in [-1, 1]",
      },
      { label: "Scope", value: "Cross-asset" },
    ],
  },

  scoring: {
    steps: [
      "Each raw metric is transformed with a blend of rolling robust normalization (median / MAD over a long lookback) and expanding-history percentile context, producing a signed signal in [-1, 1] and a 0-1 attention term.",
      "Per-category signal and attention are reliability-weighted means of available metrics, then nudged by sign-consensus and cross-metric dispersion boosts.",
      "Category weights are reliability- and coverage-adjusted and re-normalized each day, so missing inputs don't silently bias the headline.",
      "cycle_extension_score = expanding-percentile blend of (50d/350d, price/200d, price/200w, 1y ROI) with weights 0.30, 0.20, 0.35, 0.15.",
      "trend_composite_score = confidence-aware blend of BTC signal (70%) and total market signal (30%); used as context only.",
      "Signals agreeing = 0.70 × BTC attention + 0.30 × total-market attention, after the per-category consensus/dispersion boosts.",
      "confidence_score = 0.7 × btc_confidence + 0.3 × total_market_confidence, where each confidence = mean of coverage and reliability.",
      "The peaks and bottoms scores align cycle p_frenzy / p_accumulation scores against long-horizon labels; the latest Phase 2 evidence blocks promoted probability, leakage-sensitive, and live-style claims until the gates pass.",
    ],
  },
};

export const CURATED_METRICS = [
  {
    key: "trend_extension",
    copyKey: "btc_trend_extension",
    btcColumn: "metric_btc_trend_extension_50d_350d__btc__price_structure_signal",
    totalColumn: "metric_total_trend_extension_50d_350d__btc__total_market_context_signal",
  },
  {
    key: "log_reg",
    copyKey: "btc_log_reg_deviation",
    btcColumn: "metric_btc_log_reg_deviation__btc__price_structure_signal",
    totalColumn: "metric_total_log_reg_deviation__btc__total_market_context_signal",
  },
  {
    key: "drawdown",
    copyKey: "btc_drawdown_from_ath",
    btcColumn: "metric_btc_drawdown_from_ath__btc__price_structure_signal",
    totalColumn: null,
  },
  {
    key: "realized_vol",
    copyKey: "btc_realized_vol",
    btcColumn: "metric_btc_realized_vol_30d__btc__price_structure_signal",
    totalColumn: null,
  },
  {
    key: "fear_greed",
    copyKey: "fear_greed",
    btcColumn: "metric_fear_greed_index__both__fear_greed_signal",
    totalColumn: null,
  },
  {
    key: "dominance",
    copyKey: "btc_dominance",
    btcColumn: "metric_btc_dominance_proxy__both__total_market_context_signal",
    totalColumn: null,
  },
  {
    key: "mvrv",
    copyKey: "mvrv_ratio_z_proxy",
    btcColumn: "metric_mvrv_ratio_z_proxy__both__onchain_signal",
    totalColumn: null,
  },
];
