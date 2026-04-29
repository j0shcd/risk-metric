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
  generated_at: "2026-04-24T06:00:00Z",
  schema_version: "1.0.0",
  version: "v1",
  index_name: "date",
  index: ["2026-04-22", "2026-04-23", "2026-04-24"],
  columns: {
    category_price_structure_heat_contribution: [0.1, 0.2, 0.3],
  },
};

const fixtures = {
  "manifest.json": {
    version: "v1",
    schema_version: "1.0.0",
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
  "latest_snapshot.json": {
    generated_at: "2026-04-24T06:00:00Z",
    schema_version: "1.0.0",
    version: "v1",
    date: "2026-04-24",
    btc_risk: { heat: 0.21, attention: 0.44, confidence: 0.62, coverage: 0.55 },
    total_market_risk: { heat: 0.16, attention: 0.39, confidence: 0.54, coverage: 0.48 },
    headline_attention: 0.42,
    headline_heat: 0.09,
    confidence_score: 0.58,
    cycle_model: {
      heat_score: 0.68,
      cold_score: 0.32,
      p_frenzy: 0.61,
      p_accumulation: 0.38,
      confidence: 0.74,
      position: 1,
      signal_regime: "HOLD",
    },
  },
  "history_core.json": {
    generated_at: "2026-04-24T06:00:00Z",
    schema_version: "1.0.0",
    version: "v1",
    index_name: "date",
    index: ["2026-04-22", "2026-04-23", "2026-04-24"],
    columns: {
      headline_heat: [0.03, 0.07, 0.09],
      headline_attention: [0.34, 0.39, 0.42],
      confidence_score: [0.6, 0.59, 0.58],
      cycle_heat_score: [0.58, 0.63, 0.68],
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
      metric_a_heat_contribution: [0.12, 0.13, 0.14],
      metric_b_heat_contribution: [-0.05, -0.06, -0.07],
    },
  },
  "metric_breakdowns_total_market.json": {
    ...baseColumnar,
    columns: {
      metric_c_heat_contribution: [0.03, 0.04, 0.05],
      metric_d_heat_contribution: [-0.02, -0.01, -0.03],
    },
  },
  "diagnostics.json": {
    generated_at: "2026-04-24T06:00:00Z",
    schema_version: "1.0.0",
    version: "v1",
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

  it("renders Focus by default and shows Debug content when switched", async () => {
    render(<App />);

    expect(await screen.findByText("RISK METRIC")).toBeInTheDocument();
    expect(await screen.findByText("Headline Heat + Headline Attention")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /^Reset Zoom$/ }).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Cycle Regime Index").length).toBeGreaterThan(0);
    await waitFor(() => {
      expect(screen.getByText(/LAST PRINT/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("tab", { name: "Debug" }));

    expect(await screen.findByText("System Diagnostics")).toBeInTheDocument();
    expect(screen.getByText("Benchmark KPIs")).toBeInTheDocument();
    expect(screen.getByText("Label Comparison (Recent)")).toBeInTheDocument();
    expect(screen.getByText("Category — BTC")).toBeInTheDocument();
    expect(screen.getAllByTestId("chart").length).toBeGreaterThan(0);
  });

  it("renders diagnostics even when benchmark payload is missing", async () => {
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
            generated_at: "2026-04-24T06:00:00Z",
            schema_version: "1.0.0",
            version: "v1",
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
    fireEvent.click(await screen.findByRole("tab", { name: "Debug" }));

    expect(await screen.findByText("System Diagnostics")).toBeInTheDocument();
    expect(screen.getByText("Benchmark KPIs")).toBeInTheDocument();
  });
});
