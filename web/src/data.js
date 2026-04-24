const ARTIFACT_ROOT = "/data/v1";

const FALLBACK_MODES = new Set([
  "local_cache",
  "coingecko_global_latest",
  "coinmetrics_community",
  "apple_rss_top_free",
]);

const UNAVAILABLE_MODES = new Set(["unavailable", "disabled", "unknown"]);

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

function lastFinite(values = []) {
  for (let idx = values.length - 1; idx >= 0; idx -= 1) {
    const num = toNumber(values[idx]);
    if (num !== null) {
      return num;
    }
  }
  return null;
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
  const names = Object.keys(columns).filter((name) => name.endsWith("_heat_contribution"));

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
