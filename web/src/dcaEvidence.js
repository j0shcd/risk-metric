export const DCA_EVIDENCE = Object.freeze({
  evaluatedAt: "2026-08-01",
  dataWindow: "2014-12-31 → 2026-07-31",
  runId: "dca-evidence-three-tests",
  headline: "Useful for de-risking. Not proven for timing buys.",
  summary:
    "The current score helped manage an existing Bitcoin position in historical simulations, but varying monthly purchases did not beat simply buying every month. The independent four-year signal test is still underpowered and points the wrong way.",
  tests: [
    {
      id: "accumulation",
      number: "01",
      title: "Accumulation only",
      verdict: "Not supported",
      tone: "red",
      featuredValue: "−21.46%",
      featuredLabel: "median ending wealth vs Fixed DCA",
      explanation:
        "Every strategy received the same monthly deposits and selling was prohibited. Deferring purchases cost more than the lower-risk entries recovered.",
      stats: [
        ["Windows tested", "93"],
        ["Beat Fixed DCA", "26.88%"],
        ["Cash yield", "3% yearly"],
      ],
    },
    {
      id: "derisking",
      number: "02",
      title: "De-risking one BTC",
      verdict: "Historically promising",
      tone: "green",
      featuredValue: "90.32%",
      featuredLabel: "of windows had a better Calmar ratio than hold",
      explanation:
        "Each simulation began with one BTC and no new deposits. Risk-based selling and re-entry improved the return-to-drawdown trade-off in most historical windows.",
      stats: [
        ["Beat hold on wealth", "68.82%"],
        ["Median drawdown reduction", "24.18 pp"],
        ["Windows tested", "93"],
      ],
    },
    {
      id: "signal",
      number: "03",
      title: "Four-year region test",
      verdict: "Not supported",
      tone: "red",
      featuredValue: "1",
      featuredLabel: "effective non-overlapping observation",
      explanation:
        "Low- and high-risk regions were compared without a trading policy. The return ordering was wrong and the available Bitcoin history is too short for a reliable four-year statistical conclusion.",
      stats: [
        ["Horizon", "48 months"],
        ["Low minus high return", "−938.61%"],
        ["Timing-placebo p", "0.881"],
      ],
    },
  ],
  attribution: [
    ["Fixed monthly buys", "Baseline", "—"],
    ["Risk-varying buys", "−21.46%", "26.88%"],
    ["Fixed buys + risk sells", "−9.23%", "5.38%"],
    ["Risk buys + risk sells", "−26.01%", "26.88%"],
  ],
  safeguards: [
    "Every decision uses the previous month’s risk reading.",
    "Future-score and future-price mutations cannot change earlier trades.",
    "Accumulation comparisons use identical deposits, costs, and cash yield.",
    "The independent signal horizon is locked at 48 months.",
  ],
});
