import { describe, expect, it, vi } from "vitest";

import { loadDashboardData, loadMethodData } from "./data";

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
  it("loads only the four initial artifacts", async () => {
    global.fetch = vi.fn(async (url) => ({ ok: true, json: async () => base[String(url).split("/").pop()] }));
    const out = await loadDashboardData();
    expect(global.fetch.mock.calls.map(([url]) => url)).toEqual([
      "/data/v2/manifest.json",
      "/data/releases/release-1/latest_snapshot.json",
      "/data/releases/release-1/history_core.json",
      "/data/releases/release-1/diagnostics.json",
    ]);
    expect(Object.keys(out).sort()).toEqual(["degraded", "diagnostics", "historyCore", "latestSnapshot", "manifest"]);
  });

  it("loads Method from the requested immutable release and rejects a mixed release", async () => {
    global.fetch = vi.fn(async () => ({ ok: true, json: async () => base["metric_breakdowns_btc.json"] }));
    expect((await loadMethodData("release-1")).release_id).toBe("release-1");
    expect(global.fetch).toHaveBeenCalledWith("/data/releases/release-1/metric_breakdowns_btc.json");
    await expect(loadMethodData("release-2")).rejects.toThrow(/inconsistent release_id/);
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
