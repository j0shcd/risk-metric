export const DCA_EVIDENCE = Object.freeze({
  evaluatedAt: "2026-08-01",
  dataWindow: "2014-12-31 \u2192 2026-07-31",
  runId: "dca-evidence-three-tests",
  headline: "We tested the score three ways. It passed once.",
  summary:
    "Buying more when the reading is low did worse than just buying the same amount every month. Selling into high readings did help someone who already held Bitcoin. The third test, which checks the score on its own without any trading rules, does not have enough Bitcoin history behind it to settle anything.",
  cannotDo: [
    "It cannot tell you what happens next. Every number here is measured on history that has already happened.",
    "It cannot tell you when to buy. That is test 1, and test 1 failed.",
    "It has never been graded live. The thresholds were picked by someone who had already seen the chart.",
  ],
  tests: [
    {
      id: "accumulation",
      number: "01",
      title: "Does it help you buy?",
      verdict: "Not supported",
      tone: "red",
      featuredValue: "\u221221.46%",
      featuredLabel: "less money at the end than buying the same amount every month",
      explanation:
        "Every version got the same deposits and none of them were allowed to sell. Waiting for a lower reading cost more than the cheaper entries made back.",
      stats: [
        ["Start dates tested", "93"],
        ["Start dates it won", "26.88%"],
        ["Interest on idle cash", "3% a year"],
      ],
    },
    {
      id: "derisking",
      number: "02",
      title: "Does it help you sell?",
      verdict: "Historically promising",
      tone: "green",
      featuredValue: "90.32%",
      featuredLabel: "of start dates had a better return-per-drawdown than holding",
      explanation:
        "Each run started with one Bitcoin and no new deposits. Selling into high readings and buying back into low ones gave a smoother ride than sitting still, in most stretches of history.",
      stats: [
        ["Ended richer than holding", "68.82%"],
        ["Typical drawdown avoided", "24.18 pp"],
        ["Start dates tested", "93"],
      ],
    },
    {
      id: "signal",
      number: "03",
      title: "Is the score itself any good?",
      verdict: "Not supported",
      tone: "red",
      featuredValue: "1",
      featuredLabel: "genuinely independent four-year observation in all of Bitcoin history",
      explanation:
        "This test skips trading entirely and just asks whether low readings were followed by better four years than high ones. They were not. But four-year windows overlap so heavily that Bitcoin has only really been through this once, so the result settles nothing either way.",
      stats: [
        ["Horizon", "48 months"],
        ["Low minus high return", "\u2212938.61%"],
        ["Timing-placebo p", "0.881"],
      ],
    },
  ],
  attribution: [
    ["Same amount every month", "Baseline", "\u2014"],
    ["Buy more when low", "\u221221.46%", "26.88%"],
    ["Buy the same, sell when high", "\u22129.23%", "5.38%"],
    ["Buy more when low, sell when high", "\u221226.01%", "26.88%"],
  ],
  safeguards: [
    "Every decision uses last month\u2019s reading, never today\u2019s.",
    "Future-score and future-price mutations cannot change earlier trades.",
    "Buying comparisons use identical deposits, costs, and interest.",
    "The four-year horizon was fixed before the test ran.",
  ],
});
