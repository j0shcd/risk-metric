export const METRIC_COPY = {
  trend_composite_score: {
    shortName: "Trend Composite",
    oneLiner: "A broad background composite across structure, sentiment, and on-chain signals.",
    description:
      "Trend Composite is a broad 0-1 blend of structural, on-chain, and sentiment signals. It is useful as regime context, but it is intentionally less specific than the top and bottom reversal models. Use it as a backdrop signal rather than a standalone decision trigger.",
    notMeaning:
      "Trend Composite does not directly estimate top or bottom reversal probability.",
    technicalRows: [
      { label: "Inputs", value: "Price structure, on-chain, fear/greed, social, total market context" },
      { label: "Formula", value: "Confidence-weighted blend of BTC signal (70%) and total market signal (30%)" },
      { label: "Role", value: "Context index; reversal probabilities are modeled separately" },
    ],
  },
  cycle_extension: {
    shortName: "Cycle Extension",
    oneLiner: "How far price structure is extended versus long-run moving-average anchors.",
    description:
      "Cycle Extension is a 0-1 structural risk index built from expanding-history percentiles of four moving-average relationships. Each input is ranked against its full prior history (so a value of 1.0 means today is the most extended reading ever observed). The four percentiles are then combined with fixed weights. High values mean price structure is historically stretched to the upside.",
    notMeaning:
      "Cycle Extension is not a direct reversal-probability model and should be read together with top/bottom reversal risk.",
    technicalRows: [
      {
        label: "Inputs",
        value: "50d/350d MA ratio, price/200d MA, price/200w MA, and 1-year return",
      },
      {
        label: "Per-input transform",
        value: "Expanding-history percentile rank (uses only data available up to time t — no future leakage)",
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
    shortName: "Top Reversal Risk",
    oneLiner: "Calibrated probability-like estimate of top-side reversal conditions.",
    description:
      "Top Reversal Risk takes the cycle model's raw top-side probability (p_frenzy, itself a logistic mapping of upper-cycle valuation, speculation, attention, and macro scores) and recalibrates it against historical top-side labels using a walk-forward objective. The objective rewards early recall of true top regimes while penalizing false alarms and drawdown-equivalent costs. The output is a 0-1 score that behaves like a probability of being in a top-reversal regime.",
    notMeaning:
      "A high reading is not an immediate sell signal — timing can stay elevated for long stretches, and the model expresses regime probability, not price direction over short windows.",
    technicalRows: [
      { label: "Base input", value: "p_frenzy (cycle-model logistic on upper-cycle scores) + cycle structural features" },
      {
        label: "Labels",
        value: "Long-horizon top regimes derived from forward-drawdown thresholds (e.g. >=40% within 12 months)",
      },
      {
        label: "Calibration",
        value: "Walk-forward: each year-segment is calibrated only on prior years; no future data leaks into the score",
      },
      {
        label: "Objective",
        value: "Weighted blend of lead-recall at a fixed alert rate, PR-AUC, and drawdown-avoidance KPIs",
      },
      { label: "Output range", value: "Bounded 0-1 (higher = higher top-reversal probability)" },
    ],
  },
  bottom_reversal_risk: {
    shortName: "Bottom Reversal Risk",
    oneLiner: "Calibrated probability-like estimate of bottom-side reversal conditions.",
    description:
      "Bottom Reversal Risk applies the same walk-forward calibration pipeline as Top Reversal Risk but with the cycle model's accumulation-side probability (p_accumulation) as its base, and forward-recovery labels (price recoveries above a threshold within a forward window) as targets. The output behaves like a probability of being in a bottom/accumulation regime.",
    notMeaning:
      "A high reading is not an immediate buy signal and does not guarantee local price lows; accumulation regimes can persist for many months.",
    technicalRows: [
      { label: "Base input", value: "p_accumulation (cycle-model logistic on lower-cycle scores) + cycle structural features" },
      {
        label: "Labels",
        value: "Long-horizon bottom regimes derived from forward-recovery thresholds within a fixed horizon",
      },
      {
        label: "Calibration",
        value: "Walk-forward: each year-segment is calibrated only on prior years; no future data leaks into the score",
      },
      {
        label: "Objective",
        value: "Weighted blend of lead-recall at a fixed alert rate, PR-AUC, and recovery-capture KPIs",
      },
      { label: "Output range", value: "Bounded 0-1 (higher = higher bottom-reversal probability)" },
    ],
  },
  headline_attention: {
    shortName: "Signal Agreement",
    oneLiner: "How broadly and strongly the underlying inputs agree with each other right now.",
    description:
      "Signal Agreement measures how concentrated and emphatic the evidence is across the underlying inputs (price structure, on-chain, sentiment, social, market context). High values mean many inputs are pointing the same direction with reliable signals; low values mean inputs are mixed or quiet. It is a 'how loud is the chorus' meter, not a directional buy/sell.",
    notMeaning:
      "Signal Agreement is not a directional signal. High Signal Agreement can accompany either extreme fear or extreme euphoria — it only says the inputs are speaking emphatically.",
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
    shortName: "Cycle Regime Index",
    oneLiner: "Where the market appears to sit in the multi-year Bitcoin cycle.",
    description:
      "The Cycle Regime Index (CRI) is a slow-moving 0-1 estimate of where the current regime sits within the broader multi-year cycle. Underneath, two monthly composites — frenzy and accumulation — are each built from weighted valuation, speculation, attention, and macro percentiles. Those are mapped through logistic functions to produce p_frenzy and p_accumulation, then shrunk by a confidence factor (low coverage → pulled toward neutral). CRI summarizes this as a single 0-1 position: near 0 looks historically accumulation-like, near 1 looks historically bubble-like.",
    notMeaning:
      "CRI does not time entries or exits and does not predict how long a regime will last. It is a regime descriptor, not a trading signal.",
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
        value: "Logistic mapping of the cycle scores, then multiplied by a 0-1 confidence factor (coverage × reliability)",
      },
      { label: "CRI", value: "Slow-moving composite of these probabilities; bounded 0-1" },
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
  mvrv_z_score: {
    shortName: "MVRV Z-Score",
    oneLiner: "Market value vs. realized value, standardized.",
    description:
      "Compares BTC market cap to its on-chain 'realized cap' (the aggregate cost basis: each coin valued at the price it last moved). The difference is divided by its rolling standard deviation to produce a z-score. Historically, very high z-scores have coincided with cycle peaks; very low z-scores with cycle bottoms.",
    technicalRows: [
      {
        label: "Raw formula",
        value: "(Market Cap - Realized Cap) / std(Market Cap - Realized Cap)",
      },
      {
        label: "Normalization",
        value: "Rolling robust z-score blended with expanding-history percentile → signed signal in [-1, 1]",
      },
      { label: "Sign convention", value: "+ = market priced well above on-chain cost basis" },
      { label: "Scope", value: "BTC on-chain data" },
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
      "headline_attention (= Signal Agreement) = 0.70 × BTC attention + 0.30 × total-market attention, after the per-category consensus/dispersion boosts.",
      "confidence_score = 0.7 × btc_confidence + 0.3 × total_market_confidence, where each confidence = mean of coverage and reliability.",
      "Top/Bottom Reversal Risk are walk-forward calibrations of the cycle p_frenzy / p_accumulation probabilities against long-horizon labels — no future data leaks into any historical point on the chart.",
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
    copyKey: "mvrv_z_score",
    btcColumn: "metric_mvrv_z_score__both__onchain_signal",
    totalColumn: null,
  },
];
