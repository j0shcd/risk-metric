const ARTIFACT_ROOT = "/data/v2";

const FALLBACK_MODES = new Set([
  "local_cache",
  "coingecko_global_latest",
  "coinmetrics_community",
  "apple_rss_top_free",
]);

const UNAVAILABLE_MODES = new Set([
  "unavailable",
  "disabled",
  "unknown",
  "future_upgrade",
  "future_upgrade_local_cache",
]);

export const DEFAULT_DCA_STRATEGY = {
  buyStartRisk: 0.3,
  buyStep: 0.1,
  buyBaseAmount: 100,
  sellStartRisk: 0.6,
  sellStep: 0.1,
  sellBaseAmount: 100,
  startDate: "",
  cadence: "weekly",
  dayOfWeek: "monday",
};

const DAY_INDEX = {
  sunday: 0,
  monday: 1,
  tuesday: 2,
  wednesday: 3,
  thursday: 4,
  friday: 5,
  saturday: 6,
};

const DCA_COMPONENTS = [
  {
    key: "top_reversal_risk",
    label: "Top Reversal Risk",
    column: "top_reversal_risk",
    derivedColumn: "dca_top_reversal_component",
    lowRiskWhen: "low",
  },
  {
    key: "bottom_reversal_risk",
    label: "Bottom Reversal Risk",
    column: "bottom_reversal_risk",
    derivedColumn: "dca_bottom_reversal_component",
    lowRiskWhen: "high",
  },
  {
    key: "cycle_extension_score",
    label: "Cycle Extension",
    column: "cycle_extension_score",
    derivedColumn: "dca_cycle_extension_component",
    lowRiskWhen: "low",
  },
  {
    key: "cycle_regime_index",
    label: "Cycle Regime Index",
    column: "cycle_frenzy_score",
    derivedColumn: "dca_cycle_regime_component",
    lowRiskWhen: "low",
  },
];

async function fetchArtifact(name) {
  const response = await fetch(`${ARTIFACT_ROOT}/${name}`);
  if (!response.ok) {
    throw new Error(`Failed to load ${name}: ${response.status}`);
  }
  return response.json();
}

function toNumber(value) {
  if (value === null || value === undefined) {
    return null;
  }
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function clamp01(value) {
  const num = toNumber(value);
  if (num === null) return null;
  return Math.min(1, Math.max(0, num));
}

function lastFinite(values = []) {
  for (let idx = values.length - 1; idx >= 0; idx -= 1) {
    const num = toNumber(values[idx]);
    if (num !== null) {
      return num;
    }
  }
  return null;
}

function hasFinite(values = []) {
  return Array.isArray(values) && values.some((value) => toNumber(value) !== null);
}

export function valueLabel(value, digits = 3) {
  const num = toNumber(value);
  if (num === null) {
    return "n/a";
  }
  return num.toFixed(digits);
}

export function pickLatestContributions(columnarPayload, limit = 12) {
  const columns = columnarPayload?.columns ?? {};
  const names = Object.keys(columns).filter((name) => name.endsWith("_signal_contribution"));

  const entries = names
    .map((name) => ({
      name,
      value: lastFinite(columns[name]),
    }))
    .filter((item) => item.value !== null)
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value));

  return entries.slice(0, limit);
}

function extractSeries(columnarPayload, column) {
  if (!columnarPayload || !column) {
    return { index: [], values: [] };
  }

  const index = Array.isArray(columnarPayload.index) ? columnarPayload.index : [];
  const values = Array.isArray(columnarPayload.columns?.[column])
    ? columnarPayload.columns[column].map((item) => toNumber(item))
    : [];

  return { index, values };
}

function firstFiniteIndex(values) {
  for (let idx = 0; idx < values.length; idx += 1) {
    if (values[idx] !== null) {
      return idx;
    }
  }
  return -1;
}

export function chartData(columnarPayload, column, options = {}) {
  const { overlayPayload = null, overlayColumn = "" } = options;
  const baseSeries = extractSeries(columnarPayload, column);
  if (baseSeries.index.length === 0) {
    return { labels: [], values: [], overlayValues: [] };
  }

  const start = firstFiniteIndex(baseSeries.values);
  if (start < 0) {
    return { labels: [], values: [], overlayValues: [] };
  }

  const labels = baseSeries.index.slice(start);
  const values = baseSeries.values.slice(start);

  if (!overlayPayload || !overlayColumn) {
    return { labels, values, overlayValues: [] };
  }

  const overlaySeries = extractSeries(overlayPayload, overlayColumn);
  const overlayMap = new Map();
  for (let idx = 0; idx < overlaySeries.index.length; idx += 1) {
    overlayMap.set(overlaySeries.index[idx], overlaySeries.values[idx] ?? null);
  }
  const overlayValues = labels.map((label) => overlayMap.get(label) ?? null);

  return { labels, values, overlayValues };
}

export function listColumns(columnarPayload) {
  if (!columnarPayload?.columns) {
    return [];
  }
  return Object.keys(columnarPayload.columns);
}

function expandingMinMaxRisk(values, lowRiskWhen) {
  let min = null;
  let max = null;

  return values.map((value) => {
    const num = clamp01(value);
    if (num === null) return null;

    min = min === null ? num : Math.min(min, num);
    max = max === null ? num : Math.max(max, num);

    const normalized = max === min ? 0.5 : (num - min) / (max - min);
    const risk = lowRiskWhen === "high" ? 1 - normalized : normalized;
    return Math.min(1, Math.max(0, risk));
  });
}

export function buildDcaRiskSeries(historyCore) {
  const labels = Array.isArray(historyCore?.index) ? historyCore.index : [];
  if (!labels.length) {
    return { labels: [], values: [], components: [] };
  }

  const hasExportedDca = hasFinite(historyCore?.columns?.dca_risk);
  const components = DCA_COMPONENTS.map((component) => {
    const exportedValues = hasFinite(historyCore?.columns?.[component.derivedColumn])
      ? historyCore.columns[component.derivedColumn].map((value) => clamp01(value))
      : null;
    const rawValues = Array.isArray(historyCore?.columns?.[component.column]) ? historyCore.columns[component.column] : [];
    return {
      ...component,
      values: exportedValues ?? expandingMinMaxRisk(rawValues, component.lowRiskWhen),
    };
  });

  const values = hasExportedDca
    ? historyCore.columns.dca_risk.map((value) => clamp01(value))
    : labels.map((_, idx) => {
        const finite = components
          .map((component) => toNumber(component.values[idx]))
          .filter((value) => value !== null);
        if (!finite.length) return null;
        return finite.reduce((sum, value) => sum + value, 0) / finite.length;
      });

  return { labels, values, components };
}

function positiveNumber(value, fallback) {
  const num = Number(value);
  return Number.isFinite(num) && num > 0 ? num : fallback;
}

function thresholdNumber(value, fallback) {
  const num = Number(value);
  return Number.isFinite(num) ? Math.min(1, Math.max(0, num)) : fallback;
}

export function normalizeDcaStrategy(strategy = {}, labels = []) {
  const merged = { ...DEFAULT_DCA_STRATEGY, ...strategy };
  const firstLabel = labels.find(Boolean) ?? "";
  const cadence = ["daily", "weekly", "monthly"].includes(merged.cadence) ? merged.cadence : DEFAULT_DCA_STRATEGY.cadence;
  const dayOfWeek = Object.prototype.hasOwnProperty.call(DAY_INDEX, merged.dayOfWeek)
    ? merged.dayOfWeek
    : DEFAULT_DCA_STRATEGY.dayOfWeek;

  return {
    buyStartRisk: thresholdNumber(merged.buyStartRisk, DEFAULT_DCA_STRATEGY.buyStartRisk),
    buyStep: positiveNumber(merged.buyStep, DEFAULT_DCA_STRATEGY.buyStep),
    buyBaseAmount: positiveNumber(merged.buyBaseAmount, DEFAULT_DCA_STRATEGY.buyBaseAmount),
    sellStartRisk: thresholdNumber(merged.sellStartRisk, DEFAULT_DCA_STRATEGY.sellStartRisk),
    sellStep: positiveNumber(merged.sellStep, DEFAULT_DCA_STRATEGY.sellStep),
    sellBaseAmount: positiveNumber(merged.sellBaseAmount, DEFAULT_DCA_STRATEGY.sellBaseAmount),
    startDate: /^\d{4}-\d{2}-\d{2}$/.test(String(merged.startDate || "")) ? merged.startDate : firstLabel,
    cadence,
    dayOfWeek,
  };
}

export function dcaActionForRisk(risk, strategy = DEFAULT_DCA_STRATEGY) {
  const value = toNumber(risk);
  if (value === null) {
    return { side: "hold", multiplier: 0, amount: 0, label: "Hold" };
  }

  if (value < strategy.buyStartRisk) {
    const multiplier = Math.max(1, Math.ceil((strategy.buyStartRisk - value) / strategy.buyStep));
    const amount = multiplier * strategy.buyBaseAmount;
    return { side: "buy", multiplier, amount, label: `Buy ${multiplier}x` };
  }

  if (value > strategy.sellStartRisk) {
    const multiplier = Math.max(1, Math.ceil((value - strategy.sellStartRisk) / strategy.sellStep));
    const amount = multiplier * strategy.sellBaseAmount;
    return { side: "sell", multiplier, amount, label: `Sell ${multiplier}x` };
  }

  return { side: "hold", multiplier: 0, amount: 0, label: "Hold" };
}

function cadenceKey(dateLabel, cadence) {
  if (cadence === "daily") return dateLabel;

  const date = new Date(`${dateLabel}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return dateLabel;

  if (cadence === "monthly") {
    return dateLabel.slice(0, 7);
  }

  const start = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  const dayOfYear = Math.floor((date - start) / 86400000) + 1;
  const week = Math.ceil((dayOfYear + start.getUTCDay()) / 7);
  return `${date.getUTCFullYear()}-W${String(week).padStart(2, "0")}`;
}

function parseDateLabel(dateLabel) {
  const date = new Date(`${dateLabel}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function isScheduledDate(dateLabel, cadence, dayOfWeek) {
  if (cadence === "daily") return true;

  const date = parseDateLabel(dateLabel);
  if (!date) return true;
  if (date.getUTCDay() !== DAY_INDEX[dayOfWeek]) return false;

  if (cadence === "weekly") return true;

  const month = date.getUTCMonth();
  const year = date.getUTCFullYear();
  for (let day = 1; day < date.getUTCDate(); day += 1) {
    const candidate = new Date(Date.UTC(year, month, day));
    if (candidate.getUTCDay() === DAY_INDEX[dayOfWeek]) {
      return false;
    }
  }
  return true;
}

export function simulateDcaStrategy(dcaSeries, strategyInput = {}) {
  const labels = Array.isArray(dcaSeries?.labels) ? dcaSeries.labels : [];
  const values = Array.isArray(dcaSeries?.values) ? dcaSeries.values : [];
  const prices = Array.isArray(dcaSeries?.priceValues) ? dcaSeries.priceValues : [];
  const strategy = normalizeDcaStrategy(strategyInput, labels);
  const warnings = [];
  if (strategy.buyStartRisk >= strategy.sellStartRisk) {
    warnings.push("Buy threshold should be below sell threshold.");
  }
  const seenCadence = new Set();
  let units = 0;
  let openCostBasis = 0;

  const rows = labels.map((date, idx) => {
    const risk = toNumber(values[idx]);
    const price = toNumber(prices[idx]);
    const active = !strategy.startDate || date >= strategy.startDate;
    const key = cadenceKey(date, strategy.cadence);
    const scheduled = isScheduledDate(date, strategy.cadence, strategy.dayOfWeek);
    const cadenceDate = active && scheduled && !seenCadence.has(key);
    if (active && scheduled) {
      seenCadence.add(key);
    }
    const desiredAction = active && cadenceDate ? dcaActionForRisk(risk, strategy) : dcaActionForRisk(null, strategy);
    const row = {
      date,
      risk,
      price,
      active,
      cadenceDate,
      desiredAmount: desiredAction.amount,
      requestedSide: desiredAction.side,
      unitsDelta: 0,
      realizedPnl: 0,
      unitsHeld: units,
      positionValue: price === null ? null : units * price,
      averageCostBasis: units > 0 ? openCostBasis / units : null,
      capped: false,
      blockedByHoldings: false,
      ...desiredAction,
    };

    if (desiredAction.side === "buy") {
      row.amount = desiredAction.amount;
      if (price !== null && price > 0) {
        row.unitsDelta = desiredAction.amount / price;
        units += row.unitsDelta;
        openCostBasis += desiredAction.amount;
      }
    } else if (desiredAction.side === "sell") {
      if (price === null || price <= 0 || units <= 0) {
        row.side = "hold";
        row.label = units <= 0 ? "Hold (no holdings)" : "Hold";
        row.amount = 0;
        row.multiplier = 0;
        row.blockedByHoldings = units <= 0;
      } else {
        const requestedUnits = desiredAction.amount / price;
        const soldUnits = Math.min(units, requestedUnits);
        const costReduction = openCostBasis * (soldUnits / units);
        units -= soldUnits;
        openCostBasis = Math.max(0, openCostBasis - costReduction);
        row.unitsDelta = -soldUnits;
        row.amount = soldUnits * price;
        row.realizedPnl = row.amount - costReduction;
        row.capped = soldUnits < requestedUnits;
        row.label = row.capped ? `${desiredAction.label} (capped)` : desiredAction.label;
      }
    }

    row.unitsHeld = units;
    row.positionValue = price === null ? null : units * price;
    row.averageCostBasis = units > 0 ? openCostBasis / units : null;
    return row;
  });

  const activeRows = rows.filter((row) => row.active);
  const signalRows = activeRows.filter((row) => row.side !== "hold");
  const latestRiskRow = [...activeRows].reverse().find((row) => row.risk !== null) ?? null;
  const currentSignal = latestRiskRow
    ? { ...latestRiskRow, ...dcaActionForRisk(latestRiskRow.risk, strategy), cadenceDate: false }
    : null;
  const buyTotal = signalRows
    .filter((row) => row.side === "buy")
    .reduce((sum, row) => sum + row.amount, 0);
  const sellTotal = signalRows
    .filter((row) => row.side === "sell")
    .reduce((sum, row) => sum + row.amount, 0);
  const latest = currentSignal;
  const latestLedgerRow = [...activeRows].reverse().find((row) => row.price !== null) ?? null;
  const totalUnitsBought = signalRows
    .filter((row) => row.side === "buy")
    .reduce((sum, row) => sum + Math.max(0, row.unitsDelta), 0);
  const totalUnitsSold = signalRows
    .filter((row) => row.side === "sell")
    .reduce((sum, row) => sum + Math.abs(Math.min(0, row.unitsDelta)), 0);
  const realizedPnl = signalRows
    .filter((row) => row.side === "sell")
    .reduce((sum, row) => sum + row.realizedPnl, 0);

  return {
    strategy,
    rows,
    signalRows,
    latest,
    warnings,
    summary: {
      buySignals: signalRows.filter((row) => row.side === "buy").length,
      sellSignals: signalRows.filter((row) => row.side === "sell").length,
      buyTotal,
      sellTotal,
      sellProceeds: sellTotal,
      savedCash: sellTotal,
      realizedPnl,
      netFlow: buyTotal - sellTotal,
      totalUnitsBought,
      totalUnitsSold,
      unitsHeld: latestLedgerRow?.unitsHeld ?? 0,
      positionValue: latestLedgerRow?.positionValue ?? null,
      averageCostBasis: latestLedgerRow?.averageCostBasis ?? null,
    },
  };
}

function buildDegradedSummary(latestSnapshot, diagnostics) {
  const sourceModes = Array.isArray(diagnostics?.source_modes) ? diagnostics.source_modes : [];
  const modeValues = sourceModes.map((item) => String(item.mode || "unknown"));

  const fallbackCount = modeValues.filter((mode) => FALLBACK_MODES.has(mode)).length;
  const unavailableCount = modeValues.filter((mode) => UNAVAILABLE_MODES.has(mode)).length;

  const confidenceScore = toNumber(latestSnapshot?.confidence_score);
  const lowConfidence = confidenceScore !== null && confidenceScore < 0.6;

  const reasons = [];
  if (fallbackCount > 0) {
    reasons.push(`${fallbackCount} fallback source mode${fallbackCount > 1 ? "s" : ""}`);
  }
  if (unavailableCount > 0) {
    reasons.push(`${unavailableCount} unavailable source mode${unavailableCount > 1 ? "s" : ""}`);
  }
  if (lowConfidence) {
    reasons.push("confidence score below 0.60");
  }

  return {
    fallbackCount,
    unavailableCount,
    lowConfidence,
    reasons,
    isDegraded: reasons.length > 0,
  };
}

export async function loadDashboardData() {
  const manifest = await fetchArtifact("manifest.json");

  const [latestSnapshot, historyCore, categoryBtc, categoryTotal, metricBtc, metricTotal, diagnostics] =
    await Promise.all([
      fetchArtifact("latest_snapshot.json"),
      fetchArtifact("history_core.json"),
      fetchArtifact("category_breakdowns_btc.json"),
      fetchArtifact("category_breakdowns_total_market.json"),
      fetchArtifact("metric_breakdowns_btc.json"),
      fetchArtifact("metric_breakdowns_total_market.json"),
      fetchArtifact("diagnostics.json"),
    ]);

  return {
    manifest,
    latestSnapshot,
    historyCore,
    categoryBtc,
    categoryTotal,
    metricBtc,
    metricTotal,
    diagnostics,
    degraded: buildDegradedSummary(latestSnapshot, diagnostics),
  };
}
