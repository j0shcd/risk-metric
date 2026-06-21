import { describe, expect, it } from "vitest";

import { buildDcaRiskSeries, chartData, dcaActionForRisk, simulateDcaStrategy } from "./data";

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

  it("simulates only the selected cadence after the start date", () => {
    const simulation = simulateDcaStrategy(
      {
        labels: ["2026-01-05", "2026-01-06", "2026-01-12", "2026-01-13"],
        values: [0.1, 0.1, 0.1, 0.1],
        priceValues: [100, 100, 200, 200],
      },
      { startDate: "2026-01-05", cadence: "weekly", dayOfWeek: "monday", buyStartRisk: 0.3, buyStep: 0.1, buyBaseAmount: 50 },
    );

    expect(simulation.signalRows.map((row) => row.date)).toEqual(["2026-01-05", "2026-01-12"]);
    expect(simulation.summary.buyTotal).toBe(200);
    expect(simulation.summary.unitsHeld).toBe(1.5);
    expect(simulation.summary.averageCostBasis).toBeCloseTo(200 / 1.5);
  });

  it("caps sales at available holdings and tracks saved cash", () => {
    const simulation = simulateDcaStrategy(
      {
        labels: ["2026-01-05", "2026-01-12", "2026-01-19"],
        values: [0.1, 0.9, 0.9],
        priceValues: [100, 100, 100],
      },
      {
        startDate: "2026-01-05",
        cadence: "weekly",
        dayOfWeek: "monday",
        buyStartRisk: 0.3,
        buyStep: 0.1,
        buyBaseAmount: 50,
        sellStartRisk: 0.6,
        sellStep: 0.1,
        sellBaseAmount: 200,
      },
    );

    expect(simulation.summary.buyTotal).toBe(100);
    expect(simulation.summary.sellTotal).toBe(100);
    expect(simulation.summary.sellProceeds).toBe(100);
    expect(simulation.summary.realizedPnl).toBe(0);
    expect(simulation.summary.unitsHeld).toBe(0);
    expect(simulation.signalRows.map((row) => row.side)).toEqual(["buy", "sell"]);
  });

  it("separates sell proceeds from realized profit", () => {
    const simulation = simulateDcaStrategy(
      {
        labels: ["2026-01-05", "2026-01-12"],
        values: [0.1, 0.9],
        priceValues: [100, 150],
      },
      {
        startDate: "2026-01-05",
        cadence: "weekly",
        dayOfWeek: "monday",
        buyStartRisk: 0.3,
        buyStep: 0.1,
        buyBaseAmount: 50,
        sellStartRisk: 0.6,
        sellStep: 0.1,
        sellBaseAmount: 150,
      },
    );

    expect(simulation.summary.sellProceeds).toBe(150);
    expect(simulation.summary.realizedPnl).toBe(50);
  });

  it("warns when buy and sell thresholds overlap", () => {
    const simulation = simulateDcaStrategy(
      { labels: ["2026-01-01"], values: [0.5] },
      { buyStartRisk: 0.7, sellStartRisk: 0.6 },
    );

    expect(simulation.warnings).toContain("Buy threshold should be below sell threshold.");
  });

  it("keeps exact threshold values as hold", () => {
    expect(dcaActionForRisk(0.3, { buyStartRisk: 0.3, buyStep: 0.1, buyBaseAmount: 1, sellStartRisk: 0.6, sellStep: 0.1, sellBaseAmount: 1 }).side).toBe("hold");
    expect(dcaActionForRisk(0.6, { buyStartRisk: 0.3, buyStep: 0.1, buyBaseAmount: 1, sellStartRisk: 0.6, sellStep: 0.1, sellBaseAmount: 1 }).side).toBe("hold");
  });
});
