import { describe, expect, it, vi } from "vitest";

import { loadDashboardData } from "./data";

const base = {
  "manifest.json": { version: "v2", release_id: "release-1" },
  "latest_snapshot.json": { confidence_score: 0.7, release_id: "release-1" },
  "history_core.json": { index: [], columns: {}, release_id: "release-1" },
  "category_breakdowns_btc.json": { index: [], columns: {}, release_id: "release-1" },
  "category_breakdowns_total_market.json": { index: [], columns: {}, release_id: "release-1" },
  "metric_breakdowns_btc.json": { index: [], columns: {}, release_id: "release-1" },
  "metric_breakdowns_total_market.json": { index: [], columns: {}, release_id: "release-1" },
  "diagnostics.json": { source_modes: [], release_id: "release-1" },
};

describe("loadDashboardData degraded summary", () => {
  it("ignores a non-JSON SPA fallback for the optional evaluation summary", async () => {
    global.fetch = vi.fn(async (url) => {
      const key = String(url).split("/").pop();
      if (key === "evaluation_summary.json") {
        return {
          ok: true,
          json: async () => {
            throw new SyntaxError("Unexpected token '<'");
          },
        };
      }
      return { ok: true, json: async () => base[key] };
    });

    const out = await loadDashboardData();
    expect(out.evaluationSummary).toBeNull();
    expect(out.latestSnapshot.release_id).toBe("release-1");
  });

  it("reports a useful error when a required artifact is not JSON", async () => {
    global.fetch = vi.fn(async (url) => {
      const key = String(url).split("/").pop();
      if (key === "history_core.json") {
        return {
          ok: true,
          json: async () => {
            throw new SyntaxError("Unexpected token '<'");
          },
        };
      }
      return { ok: true, json: async () => base[key] };
    });

    await expect(loadDashboardData()).rejects.toThrow(
      "Failed to load history_core.json: response was not valid JSON",
    );
  });

  it("marks degraded for fallback/unavailable modes", async () => {
    global.fetch = vi.fn(async (url) => {
      const key = String(url).split("/").pop();
      const payload = { ...base };
      payload["diagnostics.json"] = {
        release_id: "release-1",
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
        "latest_snapshot.json": { confidence_score: 0.4, release_id: "release-1" },
        "diagnostics.json": { source_modes: [{ source: "x", mode: "cmc_api" }], release_id: "release-1" },
      };
      return { ok: true, json: async () => payload[key] };
    });

    const out = await loadDashboardData();
    expect(out.degraded.lowConfidence).toBe(true);
    expect(out.degraded.isDegraded).toBe(true);
  });

  it("rejects a mixed client release", async () => {
    global.fetch = vi.fn(async (url) => {
      const key = String(url).split("/").pop();
      const payload = { ...base, "history_core.json": { index: [], columns: {}, release_id: "release-2" } };
      return { ok: true, json: async () => payload[key] };
    });
    await expect(loadDashboardData()).rejects.toThrow(/inconsistent release_id/);
  });
});
