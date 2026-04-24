import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import App from "./App";

vi.mock("react-chartjs-2", () => ({
  Line: ({ data }) => <div data-testid="chart">{data?.datasets?.[0]?.label || "chart"}</div>,
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
    total_market_risk: { heat: -0.16, attention: 0.39, confidence: 0.54, coverage: 0.48 },
    headline_attention: 0.42,
    headline_direction: 0.09,
    confidence_score: 0.58,
  },
  "history_core.json": {
    generated_at: "2026-04-24T06:00:00Z",
    schema_version: "1.0.0",
    version: "v1",
    index_name: "date",
    index: ["2026-04-22", "2026-04-23", "2026-04-24"],
    columns: {
      headline_direction: [0.03, 0.07, 0.09],
      headline_attention: [0.34, 0.39, 0.42],
      confidence_score: [0.6, 0.59, 0.58],
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

  it("renders cards, charts, and degraded badges from static artifacts", async () => {
    render(<App />);

    expect(await screen.findByText("Crypto Risk & Attention Dashboard")).toBeInTheDocument();
    expect(await screen.findByText("BTC Risk Heat")).toBeInTheDocument();
    expect(await screen.findByText("Confidence Score")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId("degraded-badge")).toBeInTheDocument();
    });

    expect(screen.getByText("Diagnostics")).toBeInTheDocument();
    expect(screen.getAllByTestId("chart").length).toBeGreaterThan(0);
  });
});
