export const METRIC_COPY = {
  headline_heat: {
    shortName: "Heat",
    oneLiner: "How stretched the market is across structure, sentiment, and on-chain signals.",
    description:
      "Heat is a composite 0-1 index aggregating structural, on-chain, and sentiment signals to describe where the market sits relative to its historical range. A reading near 1 reflects conditions historically associated with cycle peaks: stretched valuations, crowded positioning, elevated sentiment. A reading near 0 reflects the opposite. Heat is designed to be read alongside Attention, which measures how broadly the underlying signals agree.",
    notMeaning:
      "Heat does not predict price direction or timing. It describes current positioning relative to history, nothing more.",
    technicalRows: [
      { label: "Inputs", value: "Price structure, on-chain, fear/greed, social, total market context" },
      { label: "Formula", value: "Confidence-weighted blend of BTC heat (70%) and total market heat (30%)" },
      { label: "Normalization", value: "Rolling robust normalization and bounded signed heat signal per metric" },
    ],
  },
  headline_attention: {
    shortName: "Attention",
    oneLiner: "How broadly the underlying signals agree with each other.",
    description:
      "Attention measures how broadly the input signals agree with each other. It draws on the same categories as Heat (price structure, on-chain, sentiment, social, market context) and captures whether those categories are pointing in the same direction or diverging. High Attention means most categories agree on the current level of Heat. Low Attention means the categories are mixed. Reading Heat and Attention together: high Heat with high Attention is a stronger signal than high Heat with low Attention.",
    notMeaning:
      "Attention is not a directional signal on its own. High Attention can accompany either extreme fear or extreme euphoria.",
    technicalRows: [
      { label: "Inputs", value: "Price structure, on-chain, fear/greed, social, total market context" },
      {
        label: "Formula",
        value: "Confidence-weighted blend of BTC attention (70%) and total market attention (30%)",
      },
      {
        label: "Per-category attention",
        value: "Reliability-weighted mean of available metrics within each category",
      },
    ],
  },
  cycle_regime: {
    shortName: "Cycle Regime Index",
    oneLiner: "Where the market appears to sit in the multi-year Bitcoin cycle.",
    description:
      "The Cycle Regime Index (CRI) is a slow-moving 0-1 estimate of where the current regime sits within the broader multi-year cycle. It is computed from a weighted composite of valuation, speculation, attention, and macro signals. Values near 0 suggest historically accumulation-like conditions; values near 1 suggest historically bubble-like conditions.",
    notMeaning:
      "The CRI does not time entries or exits and does not predict how long any regime will last. It is a regime descriptor, not a trading signal.",
    technicalRows: [
      {
        label: "cycle_heat_score",
        value: "Weighted monthly composite of valuation/speculation/attention/macro hot percentiles",
      },
      { label: "cycle_cold_score", value: "1 - category hot scores, aggregated with same weights" },
      {
        label: "p_bubble / p_accumulation",
        value: "Logistic mapping of heat/cold scores with confidence shrinkage",
      },
    ],
  },

  btc_drawdown_from_ath: {
    shortName: "Drawdown from ATH",
    oneLiner: "How far BTC price is from its most recent all-time high.",
    description:
      "Measures the percentage decline of BTC price from its most recent all-time high, then maps it into a signed heat channel for scoring and plotting. Higher values mean the drawdown is small (price is near its ATH). Lower values mean the drawdown is large (price is well below its ATH).",
    technicalRows: [
      { label: "Formula", value: "(BTC close / cummax(BTC close)) - 1" },
      { label: "Scope", value: "BTC price only" },
    ],
  },
  btc_trend_extension: {
    shortName: "Trend Extension (50d/350d)",
    oneLiner: "How extended BTC is relative to its long-run moving average.",
    description:
      "The ratio of BTC's 50-day moving average to its 350-day moving average, measuring how far short-term price has stretched above or below the long-run trend. High heat means the short-term average is well above the long-term average, historically associated with overextension. Low heat means short-term price is depressed relative to the long-term trend.",
    technicalRows: [
      { label: "BTC formula", value: "SMA_50(BTC close) / SMA_350(BTC close)" },
      {
        label: "Total market formula",
        value: "SMA_50(total market cap) / SMA_350(total market cap)",
      },
    ],
  },
  btc_log_reg_deviation: {
    shortName: "Log Regression Deviation",
    oneLiner: "How far BTC price deviates from its long-run logarithmic trend.",
    description:
      "Bitcoin's price on a log scale has historically followed a decelerating growth trend. This metric measures how far the current price sits above or below a log-linear regression fit over the full price history. High heat means price is well above the long-run trend; low heat means it is below it.",
    technicalRows: [
      { label: "BTC formula", value: "BTC close / exp(polyfit(log(time), log(BTC close)))" },
      { label: "Total market", value: "Same formula applied to total market cap" },
    ],
  },
  btc_realized_vol: {
    shortName: "Realized Volatility (30d)",
    oneLiner: "How volatile BTC has been over the past 30 days.",
    description:
      "Annualized standard deviation of BTC's daily log returns over a rolling 30-day window. The direction is inverted: high volatility maps to low heat (a volatile market reads as lower heat), and low volatility maps to high heat. Extended periods of low volatility have historically sometimes preceded large directional moves.",
    technicalRows: [
      { label: "Formula", value: "std(daily log returns, 30d) x sqrt(365)" },
      { label: "Heat direction", value: "Inverted: high volatility maps to low heat" },
      { label: "Scope", value: "BTC only" },
    ],
  },
  mvrv_z_score: {
    shortName: "MVRV Z-Score",
    oneLiner: "Market value vs. realized value, standardized.",
    description:
      "MVRV compares the current market cap to the aggregate cost basis of all BTC in existence (the price at which each coin last moved on-chain). The Z-Score normalizes this ratio against its historical standard deviation. High heat means the market is priced well above aggregate on-chain cost, historically associated with cycle peaks. Low heat means most coins are at or near cost basis.",
    technicalRows: [
      {
        label: "Formula",
        value: "(Market Cap - Realized Cap) / std(Market Cap - Realized Cap)",
      },
      { label: "Scope", value: "BTC on-chain data" },
    ],
  },
  fear_greed: {
    shortName: "Fear & Greed Index",
    oneLiner: "Composite crowd sentiment from alternative.me.",
    description:
      "A widely-followed composite sentiment indicator for Bitcoin, published daily by alternative.me. It combines price momentum, volatility, market volume, social media activity, and Google Trends data into a single 0-100 score. In this dashboard it is transformed into a signed heat channel used in scoring and plotting.",
    technicalRows: [
      { label: "Source", value: "alternative.me (public API)" },
      { label: "Formula", value: "Daily 0-100 score transformed into signed heat in scoring pipeline" },
    ],
  },
  btc_dominance: {
    shortName: "BTC Dominance",
    oneLiner: "BTC's relative strength within the total crypto market.",
    description:
      "Tracks BTC's relative strength within the total crypto market. Computed as BTC's price relative to its own all-time high, divided by the total market cap relative to its own all-time high. When BTC is closer to its own peak than the total market, this metric rises. When the total market is outperforming BTC (typical of altcoin-heavy rallies), it falls.",
    technicalRows: [
      {
        label: "Formula",
        value: "(BTC close / max(BTC close)) / (total market cap / max(total market cap))",
      },
      { label: "Scope", value: "Cross-asset" },
    ],
  },

  scoring: {
    steps: [
      "Each metric is transformed with rolling robust normalization and a bounded signed heat signal.",
      "Per-category heat and attention are reliability-weighted means of available metrics.",
      "Category weights are reliability-adjusted and re-normalized each day.",
      "headline_heat = confidence-aware blend of BTC heat and total market heat (70/30 anchor).",
      "headline_attention = confidence-aware blend of BTC attention and total market attention (70/30 anchor).",
      "confidence_score = 0.7 x btc_confidence + 0.3 x total_market_confidence.",
    ],
  },
};

export const CURATED_METRICS = [
  {
    key: "trend_extension",
    copyKey: "btc_trend_extension",
    btcColumn: "metric_btc_trend_extension_50d_350d__btc__price_structure_heat",
    totalColumn: "metric_total_trend_extension_50d_350d__btc__total_market_context_heat",
  },
  {
    key: "log_reg",
    copyKey: "btc_log_reg_deviation",
    btcColumn: "metric_btc_log_reg_deviation__btc__price_structure_heat",
    totalColumn: "metric_total_log_reg_deviation__btc__total_market_context_heat",
  },
  {
    key: "drawdown",
    copyKey: "btc_drawdown_from_ath",
    btcColumn: "metric_btc_drawdown_from_ath__btc__price_structure_heat",
    totalColumn: null,
  },
  {
    key: "realized_vol",
    copyKey: "btc_realized_vol",
    btcColumn: "metric_btc_realized_vol_30d__btc__price_structure_heat",
    totalColumn: null,
  },
  {
    key: "fear_greed",
    copyKey: "fear_greed",
    btcColumn: "metric_fear_greed_index__both__fear_greed_heat",
    totalColumn: null,
  },
  {
    key: "dominance",
    copyKey: "btc_dominance",
    btcColumn: "metric_btc_dominance_proxy__both__total_market_context_heat",
    totalColumn: null,
  },
  {
    key: "mvrv",
    copyKey: "mvrv_z_score",
    btcColumn: "metric_mvrv_z_score__both__onchain_heat",
    totalColumn: null,
  },
];
