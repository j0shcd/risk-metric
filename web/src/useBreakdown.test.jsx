import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useBreakdown } from "./useBreakdown";

const payloadA = {
  index: ["2026-01-01", "2026-01-02"],
  columns: {
    metric_b_heat_contribution: [0.1, 0.2],
    metric_a_heat_contribution: [0.3, 0.4],
  },
};

const overlay = {
  index: ["2026-01-01", "2026-01-02"],
  columns: { btc_price: [100, 101] },
};

describe("useBreakdown", () => {
  it("selects a heat contribution column by default and detects overlay data", () => {
    const { result } = renderHook(() => useBreakdown(payloadA, overlay, "btc_price"));
    expect(result.current.selectedColumn.endsWith("_heat_contribution")).toBe(true);
    expect(result.current.hasOverlayData).toBe(true);
  });

  it("resets selected column when payload columns change", () => {
    const { result, rerender } = renderHook(
      ({ payload }) => useBreakdown(payload, overlay, "btc_price"),
      { initialProps: { payload: payloadA } },
    );

    const first = result.current.selectedColumn;
    result.current.setSelectedColumn("metric_a_heat_contribution");

    const payloadB = {
      index: ["2026-01-01"],
      columns: { metric_new_heat_contribution: [0.5] },
    };
    rerender({ payload: payloadB });

    expect(result.current.selectedColumn).not.toBe(first);
    expect(result.current.selectedColumn).toBe("metric_new_heat_contribution");
  });
});
