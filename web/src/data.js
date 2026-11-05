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

const DCA_COMPONENTS = [
  {
    key: "top_reversal_risk",
    label: "Looks like past peaks",
    column: "top_reversal_risk",
    derivedColumn: "dca_top_reversal_component",
    lowRiskWhen: "low",
  },
  {
    key: "bottom_reversal_risk",
    label: "Unlike past bottoms",
    column: "bottom_reversal_risk",
    derivedColumn: "dca_bottom_reversal_component",
    lowRiskWhen: "high",
  },
  {
    key: "cycle_extension_score",
    label: "Price stretch",
    column: "cycle_extension_score",
    derivedColumn: "dca_cycle_extension_component",
    lowRiskWhen: "low",
  },
  {
    key: "cycle_regime_index",
    label: "Speculation and hype",
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

function hasFinite(values = []) {
  return Array.isArray(values) && values.some((value) => toNumber(value) !== null);
}

// Axis labels stay compact; tooltip prices retain their full precision in App.
// A log axis spanning a decade or more labels only 1, 2 and 5 x 10^n. A narrower
// span (e.g. two years of price) would then show a single label, so it labels
// every whole mantissa instead. Off-grid bounds such as 58,000 never get one.
export function formatPriceTick(value, logarithmic = false, span = Infinity) {
  const num = Number(value);
  if (!Number.isFinite(num) || num < 0) return "";
  if (logarithmic) {
    if (num === 0) return "";
    const mantissa = num / (10 ** Math.floor(Math.log10(num)));
    const allowed = span >= 10 ? [1, 2, 5] : [1, 2, 3, 4, 5, 6, 7, 8, 9];
    if (!allowed.some((candidate) => Math.abs(mantissa - candidate) < 1e-9)) return "";
  }
  return num >= 1000 ? `${Number((num / 1000).toFixed(2))}k` : String(Number(num.toFixed(2)));
}

const MONTH_YEAR_FORMAT = new Intl.DateTimeFormat("en-US", {
  month: "short", year: "numeric", timeZone: "UTC",
});

export function formatDateTick(value) {
  if (!value) return "";
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? "" : MONTH_YEAR_FORMAT.format(date);
}

export function valueLabel(value, digits = 3) {
  const num = toNumber(value);
  if (num === null) {
    return "n/a";
  }
  return num.toFixed(digits);
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

  const [latestSnapshot, historyCore, diagnostics] = await Promise.all([
    fetchArtifact("latest_snapshot.json", immutableRoot),
    fetchArtifact("history_core.json", immutableRoot),
    fetchArtifact("diagnostics.json", immutableRoot),
  ]);
  if ([latestSnapshot, historyCore, diagnostics].some((artifact) => artifact?.release_id !== releaseId)) {
    throw new Error("Published artifacts contain inconsistent release_id values");
  }
  return {
    manifest,
    latestSnapshot,
    historyCore,
    diagnostics,
    degraded: buildDegradedSummary(latestSnapshot, diagnostics),
  };
}

// Method uses the same immutable release as Today, even if the manifest changes later.
export async function loadMethodData(releaseId) {
  if (!releaseId) throw new Error("Method data requires release_id");
  const data = await fetchArtifact("metric_breakdowns_btc.json", `/data/releases/${encodeURIComponent(releaseId)}`);
  if (data?.release_id !== releaseId) throw new Error("Published artifacts contain inconsistent release_id values");
  return data;
}

// --- Reading context -------------------------------------------------------
// The three regions below are the model's own frozen thresholds (<=0.25 low,
// >=0.75 high) that the evidence suite tests against. They are not display
// conveniences: changing them invalidates the published evidence.

export const RISK_REGIONS = [
  { key: "low", label: "Low", min: 0, max: 0.25 },
  { key: "middle", label: "Middle", min: 0.25, max: 0.75 },
  { key: "high", label: "High", min: 0.75, max: 1 },
];

export function scoreLabel(value) {
  const num = clamp01(value);
  return num === null ? "—" : String(Math.round(num * 100));
}

export function regionForRisk(value) {
  const num = toNumber(value);
  if (num === null) return null;
  if (num <= RISK_REGIONS[0].max) return RISK_REGIONS[0];
  if (num >= RISK_REGIONS[2].min) return RISK_REGIONS[2];
  return RISK_REGIONS[1];
}

function lastFiniteIndex(values = []) {
  for (let idx = values.length - 1; idx >= 0; idx -= 1) {
    if (toNumber(values[idx]) !== null) return idx;
  }
  return -1;
}

function shiftIsoDate(iso, days) {
  const date = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return null;
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

// Labels are ascending ISO dates, so the newest entry not after `target` is the
// closest earlier reading.
function indexAtOrBefore(labels, target) {
  for (let idx = labels.length - 1; idx >= 0; idx -= 1) {
    if (labels[idx] <= target) return idx;
  }
  return -1;
}

export function readingSummary(dcaSeries) {
  const labels = dcaSeries?.labels ?? [];
  const values = dcaSeries?.values ?? [];
  const latestIndex = lastFiniteIndex(values);
  if (latestIndex < 0) return null;

  const latest = toNumber(values[latestIndex]);
  const latestDate = labels[latestIndex];
  const history = values.slice(0, latestIndex + 1).map(toNumber).filter((v) => v !== null);
  const belowCount = history.filter((value) => value < latest).length;

  const comparisons = [
    { label: "A week ago", offset: -7 },
    { label: "A month ago", offset: -30 },
    { label: "A year ago", offset: -365 },
  ]
    .map(({ label, offset }) => {
      const target = offset === 0 ? latestDate : shiftIsoDate(latestDate, offset);
      const idx = target ? indexAtOrBefore(labels, target) : -1;
      const value = idx >= 0 ? toNumber(values[idx]) : null;
      return { label, value, region: regionForRisk(value) };
    })
    .filter((entry) => entry.value !== null);

  const region = regionForRisk(latest);
  let daysInRegion = 0;
  for (let idx = latestIndex; idx >= 0; idx -= 1) {
    if (regionForRisk(values[idx])?.key !== region?.key) break;
    daysInRegion += 1;
  }

  const regionShares = RISK_REGIONS.map((entry) => ({
    ...entry,
    share: history.length
      ? history.filter((value) => regionForRisk(value)?.key === entry.key).length / history.length
      : 0,
  }));

  return {
    latest,
    latestDate,
    region,
    daysInRegion,
    observations: history.length,
    percentileBelow: history.length > 1 ? belowCount / (history.length - 1) : null,
    firstDate: labels[firstFiniteIndex(values.map(toNumber))] ?? labels[0],
    comparisons,
    regionShares,
  };
}

// This is also the Today panel's publication boundary. A previous finite value
// must never stand in for a missing reading on the newest observation.
export function isReadingAvailable(series) {
  const index = series.labels.length - 1;
  return index >= 0 && Number.isFinite(series.values[index]) && series.coverageValues?.[index] >= 0.75;
}
