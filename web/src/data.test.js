import { describe, expect, it } from "vitest";

import { chartData } from "./data";

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
