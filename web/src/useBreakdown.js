import { useEffect, useMemo, useState } from "react";
import { chartData, listColumns, pickLatestContributions } from "./data";

export function useBreakdown(payload, overlayPayload, overlayColumn) {
  const columns = useMemo(() => listColumns(payload), [payload]);
  const preferred = useMemo(
    () => columns.find((name) => name.endsWith("_heat_contribution")) || columns[0] || "",
    [columns],
  );
  const [selectedColumn, setSelectedColumn] = useState(preferred);
  const [showOverlay, setShowOverlay] = useState(false);

  useEffect(() => {
    setSelectedColumn(preferred);
  }, [preferred]);

  const series = useMemo(
    () => chartData(payload, selectedColumn, { overlayPayload, overlayColumn }),
    [payload, selectedColumn, overlayPayload, overlayColumn],
  );
  const latestContributions = useMemo(() => pickLatestContributions(payload), [payload]);
  const hasOverlayData = series.overlayValues.some((value) => value !== null);

  return {
    columns,
    selectedColumn,
    setSelectedColumn,
    showOverlay,
    setShowOverlay,
    series,
    latestContributions,
    hasOverlayData,
  };
}
