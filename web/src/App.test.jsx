import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { forwardRef } from "react";
import { vi } from "vitest";

import App from "./App";

vi.mock("react-chartjs-2", () => ({
  Line: forwardRef(({ data }, ref) => (
    <div ref={ref} data-testid="chart">{data?.datasets?.[0]?.label || "chart"}</div>
  )),
}));

const baseColumnar = {
  release_id: "release-1",
  generated_at: "2026-04-24T06:00:00Z",
  schema_version: "2.0.0",
  version: "v2",
  index_name: "date",
  index: ["2026-04-22", "2026-04-23", "2026-04-24"],
  columns: {
    category_price_structure_signal_contribution: [0.1, 0.2, 0.3],
  },
};

const fixtures = {
  "manifest.json": {
    release_id: "release-1",
    version: "v2",
    schema_version: "2.0.0",
    generated_at: "2026-04-24T06:00:00Z",
    artifacts: [
      "manifest.json",
      "latest_snapshot.json",
      "history_core.json",
      "category_breakdowns_btc.json",
      "category_breakdowns_total_market.json",
      "metric_breakdowns_btc.json",
      "metric_breakdowns_total_market.json",
      "diagnostics.json",
    ],
  },
  "evaluation_summary.json": {
    generated_at: "2026-06-22T08:00:00Z",
    schema_version: "1.0.0",
    source_run: {
      run_id: "phase2-standard-artifacts-cli-final",
      profile: "standard",
      status: "fail",
      source_generated_at: "2026-06-22T07:24:57Z",
      config_hash: "abc123",
      git_commit: "e2b8786765bfe3c493b1b8237fc191d0aa93141c",
      seed: 1729,
    },
    claim_state: {
      status: "blocked",
      headline: "Dashboard claims blocked",
      interpretation: "Phase 2 produced evidence and blockers, not promoted claims.",
      blocking_warning_count: 3,
      high_warning_count: 4,
      test_count: 13,
      pass_count: 3,
      warn_count: 5,
      fail_count: 5,
    },
    blocking_warnings: [
      {
        code: "unknown_availability",
        test_id: "temporal.live_availability",
        severity: "high",
        message: "No available_at_date column is present.",
        blocks_dashboard: true,
      },
      {
        code: "walkforward_no_initial_robust_rows",
        test_id: "robustness.walkforward_nulls",
        severity: "high",
        message: "No walk-forward label rows pass initial gates.",
        blocks_dashboard: true,
      },
    ],
    top_warnings: [
      {
        code: "practical_no_metric_policy_beats_buy_hold",
        test_id: "practical.monthly_strategy_suite",
        severity: "high",
        message: "No metric-policy strategy row beats buy-and-hold CAGR after costs.",
        blocks_dashboard: true,
      },
    ],
    test_groups: [
      {
        family: "temporal_validity",
        pass: 0,
        warn: 1,
        fail: 1,
        tests: [
          { test_id: "temporal.live_availability", status: "fail", severity: "high", summary: "Availability metadata missing." },
        ],
      },
      {
        family: "practical",
        pass: 0,
        warn: 0,
        fail: 1,
        tests: [
          { test_id: "practical.monthly_strategy_suite", status: "fail", severity: "high", summary: "Practical strategy suite failed." },
        ],
      },
    ],
    robustness: {
      walkforward_rows: 624,
      initial_robust_rows: 0,
      survives_circular_shift_null: 0,
      passes_fdr_auc: 0,
      passes_event_concentration: 455,
    },
    validity: {
      future_shift_material_advantage_label_rows: 220,
      future_shift_material_advantage_probe_rows: 454,
      label_cluster_pass_rows: 403,
      label_rows: 624,
    },
    strength: {
      degraded_pass_rows: 387,
      degraded_rows: 624,
      rolling_stability_pass_rows: 365,
      rolling_rows: 624,
    },
    practical: {
      metric_policy_rows: 260,
      metric_policy_beats_buy_hold_rows: 0,
      risk_weighted_dca_rows: 20,
      risk_weighted_dca_beats_fixed_rows: 0,
      best_rows: [
        {
          signal: "attention_score",
          strategy: "metric_allocation_bands",
          cost_bps: 0,
          cagr: 0.286,
          cagr_delta_vs_buy_hold: -0.667,
          max_drawdown: -0.44,
        },
      ],
    },
  },
  "latest_snapshot.json": {
    release_id: "release-1",
    generated_at: "2026-04-24T06:00:00Z",
    schema_version: "2.0.0",
    version: "v2",
    date: "2026-04-24",
    btc_risk: { signal: 0.21, attention: 0.44, confidence: 0.62, coverage: 0.55 },
    total_market_risk: { signal: 0.16, attention: 0.39, confidence: 0.54, coverage: 0.48 },
    headline_attention: 0.42,
    trend_composite_score: 0.09,
    cycle_extension_score: 0.31,
    top_reversal_risk: 0.58,
    bottom_reversal_risk: 0.41,
    attention_score: 0.42,
    confidence_score: 0.58,
    cycle_model: {
      frenzy_score: 0.68,
      accumulation_score: 0.32,
      p_frenzy: 0.61,
      p_accumulation: 0.38,
      confidence: 0.74,
      position: 1,
      signal_regime: "HOLD",
    },
  },
  "history_core.json": {
    release_id: "release-1",
    generated_at: "2026-04-24T06:00:00Z",
    schema_version: "2.0.0",
    version: "v2",
    index_name: "date",
    index: ["2026-04-22", "2026-04-23", "2026-04-24"],
    columns: {
      trend_composite_score: [0.03, 0.07, 0.09],
      headline_attention: [0.34, 0.39, 0.42],
      cycle_extension_score: [0.24, 0.28, 0.31],
      top_reversal_risk: [0.45, 0.51, 0.58],
      bottom_reversal_risk: [0.52, 0.48, 0.41],
      attention_score: [0.31, 0.37, 0.42],
      confidence_score: [0.6, 0.59, 0.58],
      cycle_frenzy_score: [0.58, 0.63, 0.68],
      cycle_confidence: [0.72, 0.73, 0.74],
      btc_price: [62000, 63500, 64000],
      total_market_cap: [2.1e12, 2.12e12, 2.15e12],
    },
  },
  "category_breakdowns_btc.json": baseColumnar,
  "category_breakdowns_total_market.json": baseColumnar,
  "metric_breakdowns_btc.json": {
    ...baseColumnar,
    columns: {
      metric_a_signal_contribution: [0.12, 0.13, 0.14],
      metric_b_signal_contribution: [-0.05, -0.06, -0.07],
      metric_btc_trend_extension_50d_350d__btc__price_structure_signal: [0.21, 0.24, 0.28],
    },
  },
  "metric_breakdowns_total_market.json": {
    ...baseColumnar,
    columns: {
      metric_c_signal_contribution: [0.03, 0.04, 0.05],
      metric_d_signal_contribution: [-0.02, -0.01, -0.03],
    },
  },
  "diagnostics.json": {
    release_id: "release-1",
    generated_at: "2026-04-24T06:00:00Z",
    schema_version: "2.0.0",
    version: "v2",
    validation: {
      passed: true,
      errors: [],
      warnings: ["Some sources are unavailable."],
    },
    source_modes: [
      { source: "btc_price", mode: "local_csv" },
      { source: "social::youtube_interest", mode: "unavailable" },
    ],
    source_health: [
      { source: "btc_price", available: true, staleness_days: 0 },
      { source: "social::youtube_interest", available: false, staleness_days: null },
    ],
    metric_health: [],
    sanity_report: [{ check: "example", passed: true, value: 1.0, threshold: 0.0 }],
    benchmark_summary: [
      {
        kpi: "lead_recall_top",
        signal: "top_reversal_risk",
        expanding: 0.45,
        recent: 0.4,
        delta_recent_minus_expanding: -0.05,
        alert_rate: 0.2,
      },
      {
        kpi: "lead_recall_bottom",
        signal: "bottom_reversal_risk",
        expanding: 0.5,
        recent: 0.55,
        delta_recent_minus_expanding: 0.05,
        alert_rate: 0.2,
      },
    ],
    benchmark_by_label: [
      {
        window: "recent",
        signal: "top_reversal_risk",
        label_id: "threshold_top_dd40_h12",
        lead_recall_at_alert_rate: 0.44,
        auc: 0.63,
      },
    ],
    benchmark_by_signal: [
      {
        window: "recent",
        signal: "top_reversal_risk",
        lead_recall_at_alert_rate: 0.44,
        pr_auc: 0.35,
        false_alarm_rate: 0.2,
      },
    ],
    benchmark_window_stats: [{ window: "expanding", side: "top", lead_recall_at_alert_rate: 0.45 }],
    benchmark_config: { alert_rate: 0.2 },
    calibration_metadata: { walkforward_last_train_end: "2026-03-31" },
  },
};

describe("App", () => {
  beforeEach(() => {
    global.fetch = vi.fn(async (url) => {
      const key = String(url).split("/").pop();
      if (!key || !(key in fixtures)) {
        return { ok: false, status: 404, json: async () => ({}) };
      }
      return {
        ok: true,
        status: 200,
        json: async () => fixtures[key],
      };
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("centers DCA Risk by default and supports tab switching", async () => {
    render(<App />);

    expect(await screen.findByText(/DATA CURRENT/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Reading 2026-04-24/i).length).toBeGreaterThan(0);
    expect(await screen.findByText("Put market risk beside your Bitcoin DCA.")).toBeInTheDocument();
    expect(screen.getByText("Risk over time")).toBeInTheDocument();
    expect(screen.getByText(/HISTORICALLY|BETWEEN BUY AND SELL ZONES|READING UNAVAILABLE/)).toBeInTheDocument();
    expect((await screen.findAllByText("Top Reversal Risk")).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: /^Reset Zoom$/ }).length).toBeGreaterThan(0);
    await waitFor(() => {
      expect(screen.getByText(/Refreshed 2026-04-24T06:00:00Z/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("tab", { name: "About" }));

    expect(await screen.findByText("Headline Indices")).toBeInTheDocument();
    expect(screen.getByText(/Scoring methodology/i)).toBeInTheDocument();
    expect(screen.getByText("MVRV Ratio Z Proxy")).toBeInTheDocument();
    expect(screen.getByText("MVRV-implied Profitability View")).toBeInTheDocument();
    expect(screen.getByText(/Display only — excluded from scoring/i)).toBeInTheDocument();
  });

  it("renders the scenario planner with configurable strategy controls", async () => {
    render(<App />);

    fireEvent.click(await screen.findByRole("tab", { name: "Scenarios" }));

    expect(await screen.findByText("Compare fixed DCA with a buy-and-sell policy.")).toBeInTheDocument();
    expect(screen.getByText("Set the comparison")).toBeInTheDocument();
    expect(screen.getByText(/Fixed DCA · hold to end/)).toBeInTheDocument();
    expect(screen.getByText(/Risk-aware DCA · buy and sell/)).toBeInTheDocument();
    expect(screen.getAllByText("Total deposits")).toHaveLength(2);
    expect(screen.getAllByText("Annualized investor return")).toHaveLength(2);
    expect(screen.getByText("Recent monthly decisions")).toBeInTheDocument();
    expect(screen.getByText(/previous month.+risk reading/i)).toBeInTheDocument();
  });

  it("shows the focused DCA evidence ledger with honest verdicts", async () => {
    render(<App />);

    fireEvent.click(await screen.findByRole("tab", { name: "Evidence" }));

    expect(await screen.findByText("Useful for de-risking. Not proven for timing buys.")).toBeInTheDocument();
    expect(screen.getByText("Accumulation only")).toBeInTheDocument();
    expect(screen.getByText("De-risking one BTC")).toBeInTheDocument();
    expect(screen.getByText("Four-year region test")).toBeInTheDocument();
    expect(screen.getByText("Fixed buys + risk sells")).toBeInTheDocument();
    expect(screen.getAllByText("Not supported")).toHaveLength(2);
    expect(screen.getByText("Historically promising")).toBeInTheDocument();
    expect(screen.getByText(/previous month’s risk reading/i)).toBeInTheDocument();
  });

  it("surfaces validation failures from diagnostics", async () => {
    global.fetch = vi.fn(async (url) => {
      const key = String(url).split("/").pop();
      if (!key || !(key in fixtures)) {
        return { ok: false, status: 404, json: async () => ({}) };
      }
      if (key === "diagnostics.json") {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            ...fixtures["diagnostics.json"],
            validation: {
              passed: false,
              errors: ["Critical source contract failed: btc_price(stale:17d>3d)"],
              warnings: [],
            },
            source_health: [
              {
                source: "btc_price",
                available: true,
                contract_passed: 0,
                contract_issues: "stale:17d>3d",
                staleness_days: 17,
              },
            ],
          }),
        };
      }
      return {
        ok: true,
        status: 200,
        json: async () => fixtures[key],
      };
    });

    render(<App />);

    expect(await screen.findByText("DATA CHECK NEEDED")).toBeInTheDocument();
    expect(screen.queryByLabelText(/Data status/i)).not.toBeInTheDocument();
  });

  it("renders even when diagnostics payload is minimal", async () => {
    global.fetch = vi.fn(async (url) => {
      const key = String(url).split("/").pop();
      if (!key || !(key in fixtures)) {
        return { ok: false, status: 404, json: async () => ({}) };
      }
      if (key === "diagnostics.json") {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            release_id: "release-1",
            generated_at: "2026-04-24T06:00:00Z",
            schema_version: "2.0.0",
            version: "v2",
            validation: { passed: true, errors: [], warnings: [] },
            source_modes: [],
            source_health: [],
            metric_health: [],
            sanity_report: [],
          }),
        };
      }
      return {
        ok: true,
        status: 200,
        json: async () => fixtures[key],
      };
    });

    render(<App />);
    fireEvent.click(await screen.findByRole("tab", { name: "Method" }));

    expect((await screen.findAllByText("Trend Extension (50d/350d)")).length).toBeGreaterThan(0);
  });
});
