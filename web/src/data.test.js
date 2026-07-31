import { describe, expect, it } from "vitest";

import {
  buildDcaRiskSeries,
  chartData,
  dcaActionForRisk,
  simulateDcaComparison,
} from "./data";

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

  it("includes exact threshold values as base actions", () => {
    expect(dcaActionForRisk(0.3, { buyStartRisk: 0.3, buyStep: 0.1, buyBaseAmount: 1, sellStartRisk: 0.6, sellStep: 0.1, sellBaseAmount: 1 })).toMatchObject({ side: "buy", amount: 1 });
    expect(dcaActionForRisk(0.6, { buyStartRisk: 0.3, buyStep: 0.1, buyBaseAmount: 1, sellStartRisk: 0.6, sellStep: 0.1, sellBaseAmount: 1 })).toMatchObject({ side: "sell", amount: 1 });
  });

  it("executes base actions when lagged scenario risk equals a threshold", () => {
    const comparison = simulateDcaComparison(
      {
        labels: ["2026-01-31", "2026-02-28", "2026-03-31"],
        values: [0.25, 0.75, 0.5],
        priceValues: [100, 100, 100],
      },
      { startDate: "2026-01-01", monthlyContribution: 100 },
    );

    expect(comparison.rows[1]).toMatchObject({ riskUsed: 0.25, buyAmount: 100 });
    expect(comparison.rows[2].riskUsed).toBe(0.75);
    expect(comparison.rows[2].sellAmount).toBeGreaterThan(0);
  });

  it("compares fixed and dynamic DCA with equal monthly external cashflows", () => {
    const comparison = simulateDcaComparison(
      {
        labels: ["2026-01-31", "2026-02-28", "2026-03-31"],
        values: [0.1, 0.9, 0.5],
        priceValues: [100, 100, 100],
      },
      { startDate: "2026-01-01", monthlyContribution: 100 },
    );

    expect(comparison.fixed.totalContributed).toBe(300);
    expect(comparison.dynamic.totalContributed).toBe(300);
    expect(comparison.rows.map((row) => row.contribution)).toEqual([100, 100, 100]);
  });

  it("warns when scenario thresholds overlap", () => {
    const comparison = simulateDcaComparison(
      { labels: ["2026-01-31"], values: [0.5], priceValues: [100] },
      { buyStartRisk: 0.7, sellStartRisk: 0.6 },
    );

    expect(comparison.warnings).toContain("Buy threshold should be below sell threshold.");
    expect(comparison.rows).toEqual([]);
    expect(dcaActionForRisk(0.5, { buyStartRisk: 0.7, sellStartRisk: 0.6 })).toMatchObject({
      side: "hold",
      label: "Invalid thresholds",
    });
  });

  it("uses each DCA Risk observation only on the next monthly execution", () => {
    const comparison = simulateDcaComparison(
      {
        labels: ["2026-01-31", "2026-02-28", "2026-03-31"],
        values: [0.1, 0.9, 0.5],
        priceValues: [100, 100, 100],
      },
      { startDate: "2026-01-01", monthlyContribution: 100 },
    );

    expect(comparison.rows[0].riskUsed).toBeNull();
    expect(comparison.rows[0].buyAmount).toBe(0);
    expect(comparison.rows[1].riskUsed).toBe(0.1);
    expect(comparison.rows[1].buyAmount).toBeGreaterThan(0);
    expect(comparison.rows[2].riskUsed).toBe(0.9);
    expect(comparison.rows[2].sellAmount).toBeGreaterThan(0);
  });

  it("does not count deposits as time-weighted investment return", () => {
    const comparison = simulateDcaComparison(
      {
        labels: ["2026-01-31", "2026-02-28", "2026-03-31"],
        values: [0.5, 0.5, 0.5],
        priceValues: [100, 100, 100],
      },
      { startDate: "2026-01-01", monthlyContribution: 100 },
    );

    expect(comparison.dynamic.timeWeightedReturn).toBeCloseTo(0);
    expect(comparison.dynamic.endingValue).toBe(300);
    expect(comparison.fixed.timeWeightedReturn).toBeLessThan(0);
  });
});
