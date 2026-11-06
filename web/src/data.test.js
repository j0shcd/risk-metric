import { describe, expect, it } from "vitest";

import {
  buildDcaRiskSeries,
  chartData,
  formatDateTick,
  formatPriceTick,
  readingSummary,
  regionForRisk,
  scoreLabel,
} from "./data";

describe("chart axis labels", () => {
  it("labels only 1, 2 and 5 times powers of ten on the log price axis", () => {
    expect([1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 20000, 100000]
      .map((value) => formatPriceTick(value, true)))
      .toEqual(["1", "2", "5", "10", "20", "50", "100", "200", "500", "1k", "2k", "5k", "20k", "100k"]);
    expect([0, 3, 4, 6, 9, 4000, 58000, 59000, 60000, 80000, 99999]
      .map((value) => formatPriceTick(value, true)))
      .toEqual(Array(11).fill(""));
    expect(formatPriceTick(0.2, true)).toBe("0.2");
  });

  it("labels every whole mantissa when the log axis spans less than a decade", () => {
    expect([58000, 60000, 70000, 90000, 100000, 130000]
      .map((value) => formatPriceTick(value, true, 130000 / 58000)))
      .toEqual(["", "60k", "70k", "90k", "100k", ""]);
  });

  it("uses compact prices without the log filter on linear axes", () => {
    expect([0, 500, 1000, 5000, 20000, 60000, 100000, 125000]
      .map((value) => formatPriceTick(value)))
      .toEqual(["0", "500", "1k", "5k", "20k", "60k", "100k", "125k"]);
    expect(formatPriceTick(1250)).toBe("1.25k");
    expect(formatPriceTick(NaN)).toBe("");
  });

  it("formats date ticks as month and year in UTC", () => {
    expect(formatDateTick("2024-11-01")).toBe("Nov 2024");
    expect(formatDateTick("2024-11-30")).toBe("Nov 2024");
    expect(formatDateTick("2025-01-01")).toBe("Jan 2025");
    expect(formatDateTick("")).toBe("");
    expect(formatDateTick("invalid")).toBe("");
  });
});

describe("chartData", () => {
  it("trims leading null values to first available datapoint", () => {
    const payload = {
      index: ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
      columns: {
        metric_a: [null, null, 0.2, 0.5],
      },
    };

    const series = chartData(payload, "metric_a");
    expect(series.labels).toEqual(["2026-01-03", "2026-01-04"]);
    expect(series.values).toEqual([0.2, 0.5]);
  });

  it("aligns overlay values to trimmed metric labels", () => {
    const payload = {
      index: ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
      columns: {
        metric_a: [null, null, 0.2, 0.5],
      },
    };
    const overlayPayload = {
      index: ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
      columns: {
        btc_price: [100, 101, 102, 103],
      },
    };

    const series = chartData(payload, "metric_a", {
      overlayPayload,
      overlayColumn: "btc_price",
    });

    expect(series.labels).toEqual(["2026-01-03", "2026-01-04"]);
    expect(series.overlayValues).toEqual([102, 103]);
  });
});

describe("DCA helpers", () => {
  it("orients aggregate risk so high bottom reversal is buy-attractive", () => {
    const series = buildDcaRiskSeries({
      index: ["2026-01-01", "2026-01-02", "2026-01-03"],
      columns: {
        top_reversal_risk: [0.5, 0.4, 0.3],
        bottom_reversal_risk: [0.5, 0.7, 0.9],
        cycle_extension_score: [0.5, 0.4, 0.3],
        cycle_frenzy_score: [0.5, 0.4, 0.3],
      },
    });

    expect(series.values[0]).toBe(0.5);
    expect(series.values[2]).toBe(0);
    expect(series.components.find((c) => c.key === "bottom_reversal_risk").values[2]).toBe(0);
  });

  it("uses exported DCA columns when present", () => {
    const series = buildDcaRiskSeries({
      index: ["2026-01-01", "2026-01-02"],
      columns: {
        dca_risk: [0.2, 0.8],
        dca_top_reversal_component: [0.1, 0.2],
        top_reversal_risk: [0.9, 0.1],
      },
    });

    expect(series.values).toEqual([0.2, 0.8]);
    expect(series.components.find((c) => c.key === "top_reversal_risk").values).toEqual([0.1, 0.2]);
  });

  it("falls back to raw metrics when exported DCA columns are all null", () => {
    const series = buildDcaRiskSeries({
      index: ["2026-01-01", "2026-01-02"],
      columns: {
        dca_risk: [null, null],
        dca_top_reversal_component: [null, null],
        top_reversal_risk: [0.4, 0.8],
        bottom_reversal_risk: [0.6, 0.8],
        cycle_extension_score: [0.2, 0.4],
        cycle_frenzy_score: [0.3, 0.5],
      },
    });

    expect(series.values[0]).toBe(0.5);
    expect(series.values[1]).not.toBeNull();
  });


});

describe("reading context", () => {
  const series = {
    labels: ["2015-01-01", "2015-06-30", "2015-12-01", "2015-12-25", "2016-01-01"],
    values: [0.1, 0.9, 0.5, 0.4, 0.3],
    coverageValues: [1, 1, 1, 1, 1],
  };

  it("scores 0-1 as a 0-100 integer", () => {
    expect(scoreLabel(0.191)).toBe("19");
    expect(scoreLabel(0.996)).toBe("100");
    expect(scoreLabel(null)).toBe("—");
  });

  it("maps values onto the model's own frozen regions", () => {
    expect(regionForRisk(0.25).key).toBe("low");
    expect(regionForRisk(0.2501).key).toBe("middle");
    expect(regionForRisk(0.7499).key).toBe("middle");
    expect(regionForRisk(0.75).key).toBe("high");
  });

  it("uses the last publishable reading, not the last finite reading", () => {
    expect(readingSummary({
      labels: ["2026-04-23", "2026-04-24"], values: [0.2, 0.8], coverageValues: [1, 0.5],
    })).toMatchObject({ latest: 0.2, latestDate: "2026-04-23" });
  });

  it("places the latest reading in its own history", () => {
    const summary = readingSummary(series);
    expect(summary.latest).toBe(0.3);
    expect(summary.latestDate).toBe("2016-01-01");
    expect(summary.region.key).toBe("middle");
    // 0.1 is the only earlier value below 0.3, out of four earlier readings.
    expect(summary.percentileBelow).toBeCloseTo(0.25);
  });

  it("reads comparisons from the nearest earlier date, not a fixed row offset", () => {
    const summary = readingSummary(series);
    const byLabel = Object.fromEntries(summary.comparisons.map((c) => [c.label, c.value]));
    expect(byLabel).not.toHaveProperty("Now");
    expect(byLabel["A week ago"]).toBe(0.4);
    expect(byLabel["A year ago"]).toBe(0.1);
  });

  it("returns null when nothing finite has been published", () => {
    expect(readingSummary({ labels: ["2015-01-01"], values: [null] })).toBeNull();
  });
});
