import { describe, expect, it } from "vitest";
import { buildDcaRiskSeries, isReadingAvailable, regionForRisk } from "./data.js";
import { buildPublicApi, PUBLIC_NOTICE } from "./publicApi.js";

const fixture = () => ({
  manifest: { release_id: "fixture" },
  latestSnapshot: { release_id: "fixture" },
  historyCore: {
    release_id: "fixture",
    index: ["2014-12-30", "2014-12-31", "2015-01-01"],
    columns: {
      dca_risk: [null, 0.41349, 0.35249],
      dca_top_reversal_component: [null, 0.11234, 0.23149],
      dca_bottom_reversal_component: [null, 0.22345, 0.34049],
      dca_cycle_extension_component: [null, null, 0.31449],
      dca_cycle_regime_component: [null, 0.44567, 0.50249],
      dca_component_coverage: [0, 0.75, 1],
    },
  },
});

describe("public JSON", () => {
  it("publishes the exact dashboard reading and component contributions to one decimal", () => {
    const input = fixture();
    const { latest, history } = buildPublicApi(input);
    expect(latest).toEqual({
      version: 1, date: "2015-01-01", reading: 35.2, region: "middle", scale: "0-100",
      regions: { low: "0-25", middle: "26-74", high: "75-100" },
      sub_scores: { looks_like_past_peaks: 23.1, unlike_past_bottoms: 34, price_stretch: 31.4, speculation_and_hype: 50.2 },
      release_id: "fixture", notice: PUBLIC_NOTICE, docs: "https://risk-metric.pages.dev/#data", status: "ok",
    });
    expect(latest.reading).toBe(Number((buildDcaRiskSeries(input.historyCore).values.at(-1) * 100).toFixed(1)));
    expect(history).toEqual({
      version: 1, scale: "0-100", release_id: "fixture", notice: PUBLIC_NOTICE,
      fields: ["date", "reading", "looks_like_past_peaks", "unlike_past_bottoms", "price_stretch", "speculation_and_hype"],
      rows: [["2014-12-31", 41.3, 11.2, 22.3, null, 44.6], ["2015-01-01", 35.2, 23.1, 34, 31.4, 50.2]],
    });
  });

  it.each([0, 0.25, 0.2501, 0.7499, 0.75, 1])("uses the page's region boundaries for %s", (value) => {
    const input = fixture();
    input.historyCore.columns.dca_risk[2] = value;
    expect(buildPublicApi(input).latest.region).toBe(regionForRisk(value).key);
  });

  it.each([0.749, 0.75])("shares the Today coverage boundary at %s", (coverage) => {
    const input = fixture();
    input.historyCore.columns.dca_component_coverage[2] = coverage;
    const available = isReadingAvailable(buildDcaRiskSeries(input.historyCore));
    const { latest } = buildPublicApi(input);
    expect(available).toBe(coverage >= 0.75);
    expect(latest.status).toBe(available ? "ok" : "unavailable");
    if (!available) {
      expect(latest.reading).toBeNull();
      expect(latest.region).toBeNull();
      expect(Object.values(latest.sub_scores)).toEqual([null, null, null, null]);
    }
  });

  it("does not republish a stale finite reading when the newest observation is missing", () => {
    const input = fixture();
    input.historyCore.columns.dca_risk[2] = null;
    const { latest, history } = buildPublicApi(input);
    expect(latest.date).toBe("2014-12-31");
    expect(latest.status).toBe("unavailable");
    expect(latest.reading).toBeNull();
    expect(latest.region).toBeNull();
    expect(Object.values(latest.sub_scores)).toEqual([null, null, null, null]);
    expect(history.rows).toHaveLength(1);
  });

  it("handles an empty series without fabricating a date or value", () => {
    const input = fixture();
    input.historyCore.index = [];
    const { latest, history } = buildPublicApi(input);
    expect(latest.date).toBeNull();
    expect(latest.status).toBe("unavailable");
    expect(history.rows).toEqual([]);
  });

  it("uses the shared fallback math, including the inverted bottoms component", () => {
    const input = fixture();
    input.historyCore.columns = {
      top_reversal_risk: [0.2, 0.4, 0.3], bottom_reversal_risk: [0.2, 0.8, 0.35],
      cycle_extension_score: [0.1, 0.9, 0.3], cycle_frenzy_score: [0.2, 0.6, 0.3],
    };
    const { latest } = buildPublicApi(input);
    expect(latest.sub_scores).toEqual({ looks_like_past_peaks: 50, unlike_past_bottoms: 75, price_stretch: 25, speculation_and_hype: 25 });
    expect(latest.reading).toBe(43.8);
  });

  it("publishes unavailable with no date when every reading is missing", () => {
    const input = fixture();
    for (const key of Object.keys(input.historyCore.columns)) {
      input.historyCore.columns[key] = [null, null, null];
    }
    const { latest, history } = buildPublicApi(input);
    expect(latest.date).toBeNull();
    expect(latest.status).toBe("unavailable");
    expect(latest.reading).toBeNull();
    expect(history.rows).toEqual([]);
  });

  it("rejects mixed releases", () => {
    const input = fixture();
    input.latestSnapshot.release_id = "other";
    expect(() => buildPublicApi(input)).toThrow(/release_id/);
  });
});
