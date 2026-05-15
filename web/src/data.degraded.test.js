import { describe, expect, it, vi } from "vitest";

import { loadDashboardData } from "./data";

const base = {
  "manifest.json": { version: "v2" },
  "latest_snapshot.json": { confidence_score: 0.7 },
  "history_core.json": { index: [], columns: {} },
  "category_breakdowns_btc.json": { index: [], columns: {} },
  "category_breakdowns_total_market.json": { index: [], columns: {} },
  "metric_breakdowns_btc.json": { index: [], columns: {} },
  "metric_breakdowns_total_market.json": { index: [], columns: {} },
  "diagnostics.json": { source_modes: [] },
};

describe("loadDashboardData degraded summary", () => {
  it("marks degraded for fallback/unavailable modes", async () => {
    global.fetch = vi.fn(async (url) => {
      const key = String(url).split("/").pop();
      const payload = { ...base };
      payload["diagnostics.json"] = {
        source_modes: [
          { source: "x", mode: "local_cache" },
          { source: "y", mode: "unavailable" },
        ],
      };
      return { ok: true, json: async () => payload[key] };
    });

    const out = await loadDashboardData();
    expect(out.degraded.isDegraded).toBe(true);
    expect(out.degraded.fallbackCount).toBe(1);
    expect(out.degraded.unavailableCount).toBe(1);
  });

  it("marks degraded for low confidence even without source mode degradation", async () => {
    global.fetch = vi.fn(async (url) => {
      const key = String(url).split("/").pop();
      const payload = {
        ...base,
        "latest_snapshot.json": { confidence_score: 0.4 },
        "diagnostics.json": { source_modes: [{ source: "x", mode: "cmc_api" }] },
      };
      return { ok: true, json: async () => payload[key] };
    });

    const out = await loadDashboardData();
    expect(out.degraded.lowConfidence).toBe(true);
    expect(out.degraded.isDegraded).toBe(true);
  });
});
