import { buildDcaRiskSeries, isReadingAvailable, readingSummary, regionForRisk, RISK_REGIONS } from "./data.js";

export const PUBLIC_NOTICE = "Describes today's market against its own history. Not a signal to buy or sell. Not investment advice.";
const COMPONENT_FIELDS = [
  ["looks_like_past_peaks", "top_reversal_risk"],
  ["unlike_past_bottoms", "bottom_reversal_risk"],
  ["price_stretch", "cycle_extension_score"],
  ["speculation_and_hype", "cycle_regime_index"],
];
const percent = (value) => Number.isFinite(value) ? Number((value * 100).toFixed(1)) : null;

export function buildPublicApi({ manifest, historyCore, latestSnapshot }) {
  const releaseId = manifest?.release_id;
  if (!releaseId || [historyCore, latestSnapshot].some((artifact) => artifact?.release_id !== releaseId)) {
    throw new Error("Published artifacts contain inconsistent release_id values");
  }
  const series = buildDcaRiskSeries(historyCore);
  const summary = readingSummary(series);
  const available = isReadingAvailable(series);
  const components = new Map(series.components.map((component) => [component.key, component.values]));
  const scoresAt = (index) => Object.fromEntries(COMPONENT_FIELDS.map(([field, key]) => [field, percent(components.get(key)?.[index])]));
  const latestIndex = series.labels.length - 1;
  const common = { version: 1, scale: "0-100", release_id: releaseId, notice: PUBLIC_NOTICE };
  const latest = {
    ...common,
    date: summary?.latestDate ?? null,
    status: available ? "ok" : "unavailable",
    reading: available ? percent(series.values[latestIndex]) : null,
    region: available ? regionForRisk(series.values[latestIndex]).key : null,
    regions: Object.fromEntries(RISK_REGIONS.map((region) => [region.key, region.rule])),
    region_basis: "unrounded reading",
    sub_scores: available ? scoresAt(latestIndex) : Object.fromEntries(COMPONENT_FIELDS.map(([field]) => [field, null])),
    docs: "https://risk-metric.pages.dev/#data",
  };
  const history = {
    ...common,
    fields: ["date", "reading", ...COMPONENT_FIELDS.map(([field]) => field)],
    rows: series.labels.flatMap((date, index) => Number.isFinite(series.values[index])
      ? [[date, percent(series.values[index]), ...Object.values(scoresAt(index))]] : []),
  };
  return { latest, history };
}
