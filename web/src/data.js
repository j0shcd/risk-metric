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
  buyStartRisk: 0.25,
  buyStep: 0.1,
  buyBaseAmount: 100,
  sellStartRisk: 0.75,
  sellStep: 0.1,
  sellBaseAmount: 100,
  startDate: "",
  cadence: "weekly",
  dayOfWeek: "monday",
};

const SCENARIO_FEE_AND_SLIPPAGE = 0.002;
const SCENARIO_MAX_BUY_MULTIPLIER = 3;
const SCENARIO_MAX_SELL_FRACTION = 0.35;
const SCENARIO_CASH_BUFFER_RATIO = 0.1;

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
    label: "Cycle Frenzy Score",
    column: "cycle_frenzy_score",
    derivedColumn: "dca_cycle_regime_component",
    lowRiskWhen: "low",
  },
];

async function fetchArtifact(name, root = ARTIFACT_ROOT) {
  const response = await fetch(`${root}/${name}`);
  if (!response.ok) {
    throw new Error(`Failed to load ${name}: ${response.status}`);
  }
  try {
    return await response.json();
  } catch {
    throw new Error(`Failed to load ${name}: response was not valid JSON`);
  }
}

async function fetchOptionalArtifact(name, fallback = null, root = ARTIFACT_ROOT) {
  const response = await fetch(`${root}/${name}`);
  if (!response.ok) {
    return fallback;
  }
  try {
    return await response.json();
  } catch {
    // Static hosts commonly rewrite missing files to index.html with a 200 status.
    return fallback;
  }
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

export function percentLabel(value, digits = 1) {
  const num = toNumber(value);
  if (num === null) {
    return "n/a";
  }
  return `${(num * 100).toFixed(digits)}%`;
}

export function integerLabel(value) {
  const num = toNumber(value);
  if (num === null) {
    return "n/a";
  }
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(num);
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

  const coverageValues = Array.isArray(historyCore?.columns?.dca_component_coverage)
    ? historyCore.columns.dca_component_coverage.map((value) => toNumber(value))
    : labels.map(
        (_, idx) => components.filter((component) => toNumber(component.values[idx]) !== null).length / components.length,
      );
  return { labels, values, components, coverageValues };
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
  if (strategy.buyStartRisk >= strategy.sellStartRisk) {
    return { side: "hold", multiplier: 0, amount: 0, label: "Invalid thresholds" };
  }
  const value = toNumber(risk);
  if (value === null) {
    return { side: "hold", multiplier: 0, amount: 0, label: "Hold" };
  }

  if (value <= strategy.buyStartRisk) {
    const multiplier = Math.max(1, Math.ceil((strategy.buyStartRisk - value) / strategy.buyStep));
    const amount = multiplier * strategy.buyBaseAmount;
    return { side: "buy", multiplier, amount, label: `Buy ${multiplier}x` };
  }

  if (value >= strategy.sellStartRisk) {
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

export function scenarioAvailableFrom(dcaSeries) {
  const labels = Array.isArray(dcaSeries?.labels) ? dcaSeries.labels : [];
  const risks = Array.isArray(dcaSeries?.values) ? dcaSeries.values : [];
  const firstRiskIndex = risks.findIndex((value) => toNumber(value) !== null);
  if (firstRiskIndex < 0 || !labels[firstRiskIndex]) return "";

  const firstRiskDate = parseDateLabel(labels[firstRiskIndex]);
  if (!firstRiskDate) return labels[firstRiskIndex];
  return new Date(Date.UTC(firstRiskDate.getUTCFullYear(), firstRiskDate.getUTCMonth() + 1, 1))
    .toISOString()
    .slice(0, 10);
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

function monthlyExecutionRows(dcaSeries) {
  const labels = Array.isArray(dcaSeries?.labels) ? dcaSeries.labels : [];
  const risks = Array.isArray(dcaSeries?.values) ? dcaSeries.values : [];
  const prices = Array.isArray(dcaSeries?.priceValues) ? dcaSeries.priceValues : [];
  const byMonth = new Map();

  labels.forEach((date, index) => {
    const price = toNumber(prices[index]);
    if (price === null || price <= 0) return;
    byMonth.set(date.slice(0, 7), {
      date,
      price,
      observedRisk: toNumber(risks[index]),
    });
  });
  return [...byMonth.values()];
}

function periodReturn(previousValue, preFlowValue, contribution, endingValue) {
  const marketFactor = previousValue > 0 ? preFlowValue / previousValue : 1;
  const postFlowValue = preFlowValue + contribution;
  const tradingFactor = postFlowValue > 0 ? endingValue / postFlowValue : 1;
  return marketFactor * tradingFactor - 1;
}

function xirr(contributions, terminalValue) {
  if (!contributions.length || !Number.isFinite(terminalValue)) return null;
  const origin = parseDateLabel(contributions[0].date);
  if (!origin) return null;
  const flows = contributions.map(({ date, amount }) => {
    const parsed = parseDateLabel(date);
    return {
      years: parsed ? (parsed - origin) / (365.2425 * 86400000) : 0,
      amount: -amount,
    };
  });
  flows[flows.length - 1].amount += terminalValue;
  if (!flows.some((flow) => flow.amount < 0) || !flows.some((flow) => flow.amount > 0)) return null;

  const npv = (rate) => flows.reduce(
    (sum, flow) => sum + flow.amount / ((1 + rate) ** flow.years),
    0,
  );
  let low = -0.9999;
  let high = 1;
  let lowValue = npv(low);
  let highValue = npv(high);
  while (Math.sign(lowValue) === Math.sign(highValue) && high < 1_000_000) {
    high *= 2;
    highValue = npv(high);
  }
  if (Math.sign(lowValue) === Math.sign(highValue)) return null;
  for (let iteration = 0; iteration < 160; iteration += 1) {
    const mid = (low + high) / 2;
    const midValue = npv(mid);
    if (Math.abs(midValue) <= 1e-10) return mid;
    if (Math.sign(midValue) === Math.sign(lowValue)) {
      low = mid;
      lowValue = midValue;
    } else {
      high = mid;
    }
  }
  return (low + high) / 2;
}

function scenarioSummary(rows, contribution) {
  const lastRow = rows.at(-1);
  const endingValue = lastRow?.value ?? 0;
  const totalContributed = rows.length * contribution;
  return {
    endingValue,
    totalContributed,
    gain: endingValue - totalContributed,
    gainOnContributions: totalContributed > 0 ? endingValue / totalContributed - 1 : null,
    timeWeightedReturn: rows.length ? rows.at(-1).twrEquity - 1 : null,
    moneyWeightedReturn: xirr(
      rows.map((row) => ({ date: row.date, amount: row.contribution })),
      endingValue,
    ),
    endingCash: lastRow?.cash ?? 0,
    endingBitcoinValue: lastRow?.bitcoinValue ?? endingValue,
    totalSold: rows.reduce((sum, row) => sum + (toNumber(row.sellAmount) ?? 0), 0),
  };
}

export function simulateDcaComparison(dcaSeries, strategyInput = {}) {
  const availableFrom = scenarioAvailableFrom(dcaSeries);
  const requestedStartDate = /^\d{4}-\d{2}-\d{2}$/.test(String(strategyInput.startDate || ""))
    ? strategyInput.startDate
    : availableFrom;
  const strategy = normalizeDcaStrategy(
    { ...strategyInput, startDate: availableFrom && requestedStartDate < availableFrom ? availableFrom : requestedStartDate },
    dcaSeries?.labels ?? [],
  );
  const contribution = positiveNumber(strategyInput.monthlyContribution, strategy.buyBaseAmount);
  const allExecutionRows = monthlyExecutionRows(dcaSeries);
  const startIndex = allExecutionRows.findIndex((row) => row.date >= strategy.startDate);
  const executionRows = startIndex >= 0 ? allExecutionRows.slice(startIndex) : [];
  const warnings = [];
  if (availableFrom && requestedStartDate < availableFrom) {
    warnings.push(`Start date moved to ${availableFrom}: DCA Risk has no prior-month reading before then.`);
  }
  if (strategy.buyStartRisk >= strategy.sellStartRisk) {
    warnings.push("Buy threshold should be below sell threshold.");
    return {
      strategy: { ...strategy, monthlyContribution: contribution },
      rows: [],
      warnings,
      fixed: scenarioSummary([], contribution),
      dynamic: scenarioSummary([], contribution),
      assumptions: {},
    };
  }

  let fixedUnits = 0;
  let fixedPreviousValue = 0;
  let fixedTwrEquity = 1;
  let dynamicCash = 0;
  let dynamicUnits = 0;
  let dynamicPreviousValue = 0;
  let dynamicTwrEquity = 1;
  let previousObservedRisk = startIndex > 0 ? allExecutionRows[startIndex - 1].observedRisk : null;
  const rows = [];

  executionRows.forEach(({ date, price, observedRisk }) => {
    const fixedPreFlow = fixedUnits * price;
    const fixedEffectivePrice = price * (1 + SCENARIO_FEE_AND_SLIPPAGE);
    fixedUnits += contribution / fixedEffectivePrice;
    const fixedValue = fixedUnits * price;
    const fixedReturn = periodReturn(fixedPreviousValue, fixedPreFlow, contribution, fixedValue);
    fixedTwrEquity *= 1 + fixedReturn;
    fixedPreviousValue = fixedValue;

    const dynamicPreFlow = dynamicCash + dynamicUnits * price;
    dynamicCash += contribution;
    let buyAmount = 0;
    let sellAmount = 0;
    const riskUsed = previousObservedRisk;
    if (riskUsed !== null && riskUsed <= strategy.buyStartRisk && strategy.buyStartRisk > 0) {
      const strength = Math.min(1, Math.max(0, (strategy.buyStartRisk - riskUsed) / strategy.buyStartRisk));
      const target = contribution * (1 + (SCENARIO_MAX_BUY_MULTIPLIER - 1) * strength);
      const equityBeforeTrade = dynamicCash + dynamicUnits * price;
      const spendable = Math.max(0, dynamicCash - SCENARIO_CASH_BUFFER_RATIO * equityBeforeTrade);
      buyAmount = Math.min(target, spendable);
      dynamicCash -= buyAmount;
      dynamicUnits += buyAmount / (price * (1 + SCENARIO_FEE_AND_SLIPPAGE));
    } else if (riskUsed !== null && riskUsed >= strategy.sellStartRisk && strategy.sellStartRisk < 1) {
      const strength = Math.min(1, Math.max(0, (riskUsed - strategy.sellStartRisk) / (1 - strategy.sellStartRisk)));
      const maximumSale = dynamicUnits * price * SCENARIO_MAX_SELL_FRACTION;
      sellAmount = Math.min(maximumSale, Math.max(contribution, maximumSale * strength));
      const unitsSold = sellAmount / price;
      dynamicUnits = Math.max(0, dynamicUnits - unitsSold);
      dynamicCash += sellAmount * (1 - SCENARIO_FEE_AND_SLIPPAGE);
    }
    const dynamicValue = dynamicCash + dynamicUnits * price;
    const dynamicReturn = periodReturn(dynamicPreviousValue, dynamicPreFlow, contribution, dynamicValue);
    dynamicTwrEquity *= 1 + dynamicReturn;
    dynamicPreviousValue = dynamicValue;

    rows.push({
      date,
      price,
      observedRisk,
      riskUsed,
      contribution,
      fixedValue,
      fixedUnits,
      fixedTwrEquity,
      dynamicValue,
      dynamicCash,
      dynamicUnits,
      dynamicTwrEquity,
      buyAmount,
      sellAmount,
    });
    previousObservedRisk = observedRisk;
  });

  return {
    strategy: { ...strategy, monthlyContribution: contribution },
    rows,
    warnings,
    fixed: scenarioSummary(
      rows.map((row) => ({
        ...row,
        value: row.fixedValue,
        twrEquity: row.fixedTwrEquity,
        cash: 0,
        bitcoinValue: row.fixedValue,
        sellAmount: 0,
      })),
      contribution,
    ),
    dynamic: scenarioSummary(
      rows.map((row) => ({
        ...row,
        value: row.dynamicValue,
        twrEquity: row.dynamicTwrEquity,
        cash: row.dynamicCash,
        bitcoinValue: row.dynamicUnits * row.price,
      })),
      contribution,
    ),
    assumptions: {
      feeAndSlippage: SCENARIO_FEE_AND_SLIPPAGE,
      maxBuyMultiplier: SCENARIO_MAX_BUY_MULTIPLIER,
      maxSellFraction: SCENARIO_MAX_SELL_FRACTION,
      cashBufferRatio: SCENARIO_CASH_BUFFER_RATIO,
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
  const releaseId = manifest?.release_id;
  if (!releaseId) throw new Error("Published manifest is missing release_id");
  const immutableRoot = `/data/releases/${encodeURIComponent(releaseId)}`;

  const [latestSnapshot, historyCore, categoryBtc, categoryTotal, metricBtc, metricTotal, diagnostics] =
    await Promise.all([
      fetchArtifact("latest_snapshot.json", immutableRoot),
      fetchArtifact("history_core.json", immutableRoot),
      fetchArtifact("category_breakdowns_btc.json", immutableRoot),
      fetchArtifact("category_breakdowns_total_market.json", immutableRoot),
      fetchArtifact("metric_breakdowns_btc.json", immutableRoot),
      fetchArtifact("metric_breakdowns_total_market.json", immutableRoot),
      fetchArtifact("diagnostics.json", immutableRoot),
    ]);
  const evaluationSummary = await fetchOptionalArtifact("evaluation_summary.json", null, immutableRoot);
  const releaseArtifacts = [latestSnapshot, historyCore, categoryBtc, categoryTotal, metricBtc, metricTotal, diagnostics];
  if (releaseArtifacts.some((artifact) => artifact?.release_id !== releaseId)) {
    throw new Error("Published artifacts contain inconsistent release_id values");
  }

  return {
    manifest,
    latestSnapshot,
    historyCore,
    categoryBtc,
    categoryTotal,
    metricBtc,
    metricTotal,
    diagnostics,
    evaluationSummary,
    degraded: buildDegradedSummary(latestSnapshot, diagnostics),
  };
}
