import { useEffect, useMemo, useRef, useState } from "react";
import {
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  LogarithmicScale,
  PointElement,
  Tooltip,
} from "chart.js";
import zoomPlugin from "chartjs-plugin-zoom";
import { Line } from "react-chartjs-2";

import {
  buildDcaRiskSeries,
  chartData,
  DEFAULT_DCA_STRATEGY,
  dcaActionForRisk,
  integerLabel,
  loadDashboardData,
  percentLabel,
  simulateDcaComparison,
  valueLabel,
} from "./data";
import { CURATED_METRICS, METRIC_COPY } from "./copy";

ChartJS.register(
  CategoryScale,
  LineElement,
  LinearScale,
  LogarithmicScale,
  PointElement,
  Tooltip,
  Legend,
  Filler,
  zoomPlugin,
);

const COLORS = {
  bg: "#0a0a0a",
  panel: "#111111",
  border: "#232323",
  borderDim: "#191919",
  text: "#cbc3ab",
  muted: "#726b5d",
  amber: "#f0a500",
  red: "#ee3333",
  green: "#22cc55",
  blue: "#5ca2ff",
  violet: "#b58cff",
};

const FONT = "'IBM Plex Mono', 'Courier New', monospace";
const PRICE_FORMAT = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const MONEY_FORMAT = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const DCA_STRATEGY_STORAGE_KEY = "riskMetricDcaStrategy.v1";
const ACTIVE_TAB_STORAGE_KEY = "riskMetricActiveTab.v1";
const TAB_KEYS = ["risk", "method", "scenarios", "evidence", "about"];

const hoverGuidePlugin = {
  id: "hoverGuide",
  afterDatasetsDraw(chart) {
    const activeElements = chart.tooltip?.getActiveElements?.() ?? [];
    if (!activeElements.length) return;

    const x = activeElements[0]?.element?.x;
    const { top, bottom } = chart.chartArea || {};
    if (!Number.isFinite(x) || !Number.isFinite(top) || !Number.isFinite(bottom)) return;

    const { ctx } = chart;
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(x, top);
    ctx.lineTo(x, bottom);
    ctx.lineWidth = 1;
    ctx.strokeStyle = "#f0a50088";
    ctx.stroke();
    ctx.restore();
  },
};

function alignOverlayValues(labels, overlaySeries) {
  const overlayMap = new Map();
  overlaySeries.labels.forEach((label, idx) => {
    overlayMap.set(label, overlaySeries.values[idx] ?? null);
  });
  return labels.map((label) => overlayMap.get(label) ?? null);
}

function formatPrice(value) {
  const num = Number(value);
  return Number.isFinite(num) ? PRICE_FORMAT.format(num) : "n/a";
}

function formatMoney(value) {
  const num = Number(value);
  return Number.isFinite(num) ? MONEY_FORMAT.format(num) : "n/a";
}

function formatDateTime(value) {
  if (!value) return "n/a";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toISOString().replace(".000Z", "Z");
}

function validationState(diagnostics) {
  const validation = diagnostics?.validation;
  if (!validation || validation.passed === undefined) {
    return { passed: null, errors: [], warnings: [] };
  }
  return {
    passed: Boolean(validation.passed),
    errors: Array.isArray(validation.errors) ? validation.errors : [],
    warnings: Array.isArray(validation.warnings) ? validation.warnings : [],
  };
}

function criticalSourceIssues(diagnostics) {
  const rows = Array.isArray(diagnostics?.source_health) ? diagnostics.source_health : [];
  return rows
    .filter((row) => row?.source === "btc_price" && row.contract_passed === 0)
    .map((row) => String(row.contract_issues || "contract failed"))
    .filter(Boolean);
}

function makeChartOptions({
  numLabels,
  hasPrice,
  priceScaleType,
  accentColor,
  yAutoScale = false,
  yDomain = [0, 1],
  showLegend = true,
}) {
  const [yMin, yMax] = yDomain;
  const yScale = {
    ...(yAutoScale ? {} : { min: yMin, max: yMax }),
    ticks: { color: COLORS.muted, font: { family: FONT, size: 10 } },
    grid: { color: COLORS.borderDim },
    border: { color: COLORS.border },
  };
  return {
    animation: false,
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    scales: {
      x: {
        ticks: { maxTicksLimit: 8, color: COLORS.muted, font: { family: FONT, size: 10 } },
        grid: { color: COLORS.borderDim },
        border: { color: COLORS.border },
      },
      y: yScale,
      yPrice: {
        display: hasPrice,
        position: "right",
        type: priceScaleType,
        ticks: {
          callback: (v) => formatPrice(v),
          color: "#8f8b80",
          font: { family: FONT, size: 10 },
        },
        grid: { drawOnChartArea: false },
        border: { color: COLORS.border },
      },
    },
    plugins: {
      legend: {
        display: showLegend,
        labels: { color: COLORS.text, font: { family: FONT, size: 11 }, boxWidth: 10 },
      },
      tooltip: {
        backgroundColor: "#090909f0",
        borderColor: COLORS.border,
        borderWidth: 1,
        titleColor: COLORS.text,
        bodyColor: COLORS.text,
        titleFont: { family: FONT, size: 11, weight: "600" },
        bodyFont: { family: FONT, size: 11 },
        callbacks: {
          title: (items) => (items.length ? `Date: ${items[0].label}` : ""),
          label: (item) =>
            item.dataset.yAxisID === "yPrice"
              ? `${item.dataset.label}: ${formatPrice(item.parsed.y)}`
              : `${item.dataset.label}: ${valueLabel(item.parsed.y, 4)}`,
        },
      },
      zoom: {
        limits: { x: { min: 0, max: Math.max(0, numLabels - 1) } },
        pan: { enabled: true, mode: "x" },
        zoom: {
          mode: "x",
          wheel: { enabled: true },
          pinch: { enabled: true },
          drag: {
            enabled: true,
            backgroundColor: `${accentColor}1f`,
            borderColor: accentColor,
            borderWidth: 1,
          },
        },
      },
    },
  };
}

function MetricCard({ label, value, tone = "amber", highlight = false }) {
  return (
    <article className={`bb-card${highlight ? " bb-card--highlight" : ""}`}>
      <p className="bb-card__label">{label}</p>
      <p className={`bb-card__value bb-card__value--${tone}`}>{valueLabel(value)}</p>
    </article>
  );
}

function CountCard({ label, value, tone = "amber", sub = "", highlight = false }) {
  return (
    <article className={`bb-card${highlight ? " bb-card--highlight" : ""}`}>
      <p className="bb-card__label">{label}</p>
      <p className={`bb-card__value bb-card__value--${tone}`}>{integerLabel(value)}</p>
      {sub && <p className="bb-card__sub">{sub}</p>}
    </article>
  );
}

function StatusTicker({ manifest, latestSnapshot, diagnostics, evaluationSummary }) {
  const validation = validationState(diagnostics);
  const sourceIssues = criticalSourceIssues(diagnostics);
  const claimsBlocked =
    evaluationSummary?.claim_state?.status === "blocked" || evaluationSummary?.source_run?.status === "fail";
  const generatedAt = manifest?.generated_at ?? latestSnapshot?.generated_at;
  const scoreDate = latestSnapshot?.date ?? "n/a";
  const isFailing = claimsBlocked || validation.passed === false || sourceIssues.length > 0;
  const statusLabel = claimsBlocked
    ? "CLAIMS BLOCKED"
    : validation.passed === null
      ? "UNVERIFIED"
      : isFailing
        ? "VALIDATION FAIL"
        : "VALIDATED";

  return (
    <header className="bb-topbar">
      <span className={`bb-live-dot${isFailing ? " bb-live-dot--fail" : ""}`} aria-hidden="true" />
      <span className={`bb-meta bb-meta--status${isFailing ? " bb-meta--fail" : ""}`}>{statusLabel}</span>
      <span className="bb-meta">SCORE DATE {scoreDate}</span>
      <span className="bb-meta">ARTIFACT {formatDateTime(generatedAt)}</span>
      <span className="bb-meta">SCHEMA {manifest?.schema_version ?? latestSnapshot?.schema_version ?? "n/a"}</span>
    </header>
  );
}

function OverviewPanel({ historyCore, setActiveTab }) {
  const chartRef = useRef(null);
  const [visible, setVisible] = useState({
    topRisk: true,
    bottomRisk: true,
    extension: false,
    attention: false,
    cycle: false,
  });
  const [priceScaleType, setPriceScaleType] = useState("logarithmic");

  const topRiskSeries = useMemo(() => chartData(historyCore, "top_reversal_risk"), [historyCore]);
  const bottomRiskValues = useMemo(
    () => alignOverlayValues(topRiskSeries.labels, chartData(historyCore, "bottom_reversal_risk")),
    [topRiskSeries.labels, historyCore],
  );
  const extensionValues = useMemo(
    () => alignOverlayValues(topRiskSeries.labels, chartData(historyCore, "cycle_extension_score")),
    [topRiskSeries.labels, historyCore],
  );
  const attnValues = useMemo(
    () => alignOverlayValues(topRiskSeries.labels, chartData(historyCore, "attention_score")),
    [topRiskSeries.labels, historyCore],
  );
  const cycleValues = useMemo(
    () => alignOverlayValues(topRiskSeries.labels, chartData(historyCore, "cycle_frenzy_score")),
    [topRiskSeries.labels, historyCore],
  );
  const btcValues = useMemo(
    () => alignOverlayValues(topRiskSeries.labels, chartData(historyCore, "btc_price")),
    [topRiskSeries.labels, historyCore],
  );

  const hasBtcData = btcValues.some((v) => v !== null);
  const showPrice = hasBtcData;

  const datasets = useMemo(() => {
    const ds = [];
    if (visible.topRisk) {
      ds.push({
        label: "Top Reversal Risk",
        data: topRiskSeries.values,
        borderColor: COLORS.red,
        borderWidth: 1.9,
        pointRadius: 0,
        fill: true,
        backgroundColor: "#ee33331f",
        tension: 0.16,
      });
    }
    if (visible.bottomRisk) {
      ds.push({
        label: "Bottom Reversal Risk",
        data: bottomRiskValues,
        borderColor: COLORS.green,
        borderWidth: 1.9,
        pointRadius: 0,
        fill: true,
        backgroundColor: "#22cc5517",
        tension: 0.16,
      });
    }
    if (visible.extension) {
      ds.push({
        label: "Cycle Extension",
        data: extensionValues,
        borderColor: COLORS.amber,
        borderWidth: 1.9,
        pointRadius: 0,
        fill: true,
        backgroundColor: "#f0a50019",
        tension: 0.16,
      });
    }
    if (visible.attention) {
      ds.push({
        label: "Signal Agreement",
        data: attnValues,
        borderColor: COLORS.blue,
        borderWidth: 1.9,
        pointRadius: 0,
        fill: true,
        backgroundColor: "#5ca2ff19",
        tension: 0.16,
      });
    }
    if (visible.cycle) {
      ds.push({
        label: "Cycle Frenzy Score",
        data: cycleValues,
        borderColor: COLORS.violet,
        borderWidth: 1.9,
        pointRadius: 0,
        fill: true,
        backgroundColor: "#b58cff19",
        tension: 0.14,
      });
    }
    if (showPrice) {
      ds.push({
        label: "BTC Price",
        data: btcValues,
        borderColor: "#8b8473",
        borderWidth: 1.3,
        pointRadius: 0,
        fill: false,
        tension: 0.12,
        yAxisID: "yPrice",
      });
    }
    return ds;
  }, [visible, topRiskSeries.values, bottomRiskValues, extensionValues, attnValues, cycleValues, btcValues, showPrice]);

  const chartPayload = useMemo(
    () => ({ labels: topRiskSeries.labels, datasets }),
    [topRiskSeries.labels, datasets],
  );

  const options = useMemo(
    () =>
      makeChartOptions({
        numLabels: topRiskSeries.labels.length,
        hasPrice: showPrice,
        priceScaleType,
        accentColor: COLORS.amber,
        showLegend: false,
      }),
    [topRiskSeries.labels.length, showPrice, priceScaleType],
  );

  function toggle(key) {
    setVisible((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  const legendItems = [
    { key: "topRisk", label: "Top Reversal Risk", color: COLORS.red },
    { key: "bottomRisk", label: "Bottom Reversal Risk", color: COLORS.green },
    { key: "extension", label: "Cycle Extension", color: COLORS.amber },
    { key: "attention", label: "Signal Agreement", color: COLORS.blue },
    { key: "cycle", label: "Cycle Frenzy Score", color: COLORS.violet },
  ];

  return (
    <section className="bb-panel bb-panel--focus">
      <div className="bb-panel__head">
        <h2 className="bb-panel__title bb-panel__title--solo">Market Indices</h2>
        <div className="bb-panel__actions">
          {showPrice && (
            <select
              className="bb-select bb-select--compact"
              value={priceScaleType}
              onChange={(e) => setPriceScaleType(e.target.value)}
            >
              <option value="logarithmic">LOG</option>
              <option value="linear">LINEAR</option>
            </select>
          )}
          <button type="button" className="bb-button" onClick={() => chartRef.current?.resetZoom?.()}>
            Reset Zoom
          </button>
        </div>
      </div>
      <div className="bb-legend" role="group" aria-label="Series visibility">
        {legendItems.map((item) => {
          const on = visible[item.key];
          return (
            <button
              key={item.key}
              type="button"
              role="switch"
              aria-checked={on}
              aria-label={`${item.label} — ${on ? "shown" : "hidden"}`}
              className={`bb-legend__item${on ? "" : " bb-legend__item--off"}`}
              onClick={() => toggle(item.key)}
            >
              <span
                className={`bb-legend__swatch${on ? "" : " bb-legend__swatch--off"}`}
                style={on ? { background: item.color } : { borderColor: item.color }}
              />
              <span className="bb-legend__label">{item.label}</span>
            </button>
          );
        })}
        {hasBtcData && (
          <span className="bb-legend__item bb-legend__item--static" aria-label="BTC Price — always shown">
            <span className="bb-legend__swatch" style={{ background: "#8b8473" }} />
            <span className="bb-legend__label">BTC Price</span>
          </span>
        )}
      </div>
      <div className="bb-chart-wrap bb-chart-wrap--focus" data-testid="overview-chart">
        {topRiskSeries.labels.length > 0 ? (
          <Line ref={chartRef} data={chartPayload} options={options} plugins={[hoverGuidePlugin]} />
        ) : (
          <p className="bb-empty">No data available.</p>
        )}
      </div>
      <div className="bb-overview-desc">
        <p>
          This dashboard tracks five 0–1 indices derived from BTC price structure, on-chain activity,
          sentiment, social signals, and total-market context. Click any legend entry above to toggle
          that series on or off.
        </p>
        <p>
          <strong>Top Reversal Risk</strong> and <strong>Bottom Reversal Risk</strong> are the
          primary signals here — bounded historical-alignment scores for top-side and bottom-side
          reversal conditions, currently under evaluation rather than promoted as validated probabilities.{" "}
          <strong>Cycle Extension</strong> measures how stretched price is
          versus long-run moving averages. <strong>Signal Agreement</strong> measures how broadly
          the underlying inputs agree with each other (high = many inputs pointing the same way; not
          a directional buy/sell). The <strong>Cycle Frenzy Score</strong> summarizes upper-cycle
          valuation, speculation, attention, and macro alignment; higher readings are more frenzy-like.
        </p>
        <p>
          All five are bounded 0–1; higher values mean stronger historical alignment with the named
          regime, not a forecast.{" "}
          <button type="button" className="bb-link" onClick={() => setActiveTab("about")}>
            Details in About →
          </button>
        </p>
        <p className="bb-overview-note">Reversal and cycle-series data begins December 2014.</p>
      </div>
    </section>
  );
}

function MetricsPanel({ metricBtc, historyCore, setActiveTab }) {
  const availableMetrics = useMemo(
    () => CURATED_METRICS.filter((m) => chartData(metricBtc, m.btcColumn).values.some((v) => v !== null)),
    [metricBtc],
  );

  const defaultKey = availableMetrics.find((m) => m.key === "trend_extension")?.key ?? availableMetrics[0]?.key;
  const [selectedKey, setSelectedKey] = useState(defaultKey);
  const [scope, setScope] = useState("btc");
  const [priceScaleType, setPriceScaleType] = useState("logarithmic");
  const chartRef = useRef(null);

  const metric = availableMetrics.find((m) => m.key === selectedKey) ?? availableMetrics[0];
  const hasTotal = !!metric && metric.totalColumn !== null;
  const copy = metric ? METRIC_COPY[metric.copyKey] : null;

  useEffect(() => {
    setScope("btc");
    chartRef.current?.resetZoom?.();
  }, [selectedKey]);

  const activeColumn = metric
    ? scope === "total" && hasTotal ? metric.totalColumn : metric.btcColumn
    : null;
  const priceColumn =
    scope === "total" && hasTotal ? "total_market_cap" : "btc_price";
  const priceLabel =
    scope === "total" && hasTotal ? "Total Market Cap" : "BTC Price";

  const series = useMemo(
    () => chartData(metricBtc, activeColumn),
    [metricBtc, activeColumn],
  );
  const priceSeries = useMemo(
    () => chartData(historyCore, priceColumn),
    [historyCore, priceColumn],
  );
  const priceValues = useMemo(
    () => alignOverlayValues(series.labels, priceSeries),
    [series.labels, priceSeries],
  );
  const hasPrice = priceValues.some((v) => v !== null);

  const chartPayload = useMemo(
    () => ({
      labels: series.labels,
      datasets: [
        {
          label: copy?.shortName ?? "",
          data: series.values,
          borderColor: COLORS.amber,
          borderWidth: 1.9,
          pointRadius: 0,
          fill: true,
          backgroundColor: "#f0a50019",
          tension: 0.16,
          yAxisID: "y",
        },
        ...(hasPrice
          ? [
              {
                label: priceLabel,
                data: priceValues,
                borderColor: "#8b8473",
                borderWidth: 1.3,
                pointRadius: 0,
                fill: false,
                tension: 0.12,
                yAxisID: "yPrice",
              },
            ]
          : []),
      ],
    }),
    [series, priceValues, hasPrice, copy?.shortName, priceLabel],
  );

  const options = useMemo(
    () =>
      makeChartOptions({
        numLabels: series.labels.length,
        hasPrice,
        priceScaleType,
        accentColor: COLORS.amber,
        yAutoScale: true,
      }),
    [series.labels.length, hasPrice, priceScaleType],
  );

  return (
    <section className="bb-panel bb-panel--focus">
      <div className="bb-panel__head">
        <div className="bb-controls-left">
          <select
            className="bb-metric-select"
            value={selectedKey}
            onChange={(e) => setSelectedKey(e.target.value)}
          >
            {availableMetrics.map((m) => (
              <option key={m.key} value={m.key}>
                {METRIC_COPY[m.copyKey].shortName}
              </option>
            ))}
          </select>
          {hasTotal && (
            <div className="bb-scope-toggle">
              <button
                type="button"
                className={`bb-scope-btn${scope === "btc" ? " bb-scope-btn--active" : ""}`}
                onClick={() => setScope("btc")}
              >
                BTC
              </button>
              <button
                type="button"
                className={`bb-scope-btn${scope === "total" ? " bb-scope-btn--active" : ""}`}
                onClick={() => setScope("total")}
              >
                Total Market
              </button>
            </div>
          )}
        </div>
        <div className="bb-panel__actions">
          {hasPrice && (
            <label className="bb-checkbox">
              PRICE SCALE
              <select
                className="bb-select bb-select--compact"
                value={priceScaleType}
                onChange={(e) => setPriceScaleType(e.target.value)}
              >
                <option value="logarithmic">LOG</option>
                <option value="linear">LINEAR</option>
              </select>
            </label>
          )}
          <button
            type="button"
            className="bb-button"
            onClick={() => chartRef.current?.resetZoom?.()}
          >
            Reset Zoom
          </button>
        </div>
      </div>
      <div className="bb-chart-wrap bb-chart-wrap--focus" data-testid="metrics-chart">
        {series.labels.length > 0 ? (
          <Line ref={chartRef} data={chartPayload} options={options} plugins={[hoverGuidePlugin]} />
        ) : (
          <p className="bb-empty">No data available for this metric.</p>
        )}
      </div>
      <div className="bb-metric-desc">
        <p className="bb-metric-desc__text">{copy?.description ?? ""}</p>
        <p className="bb-metric-desc__link">
          <button type="button" className="bb-link" onClick={() => setActiveTab("about")}>
            Details in About →
          </button>
        </p>
      </div>
    </section>
  );
}

function loadStoredDcaStrategy() {
  if (typeof window === "undefined") return DEFAULT_DCA_STRATEGY;
  try {
    const raw = window.localStorage.getItem(DCA_STRATEGY_STORAGE_KEY);
    return raw ? { ...DEFAULT_DCA_STRATEGY, ...JSON.parse(raw) } : DEFAULT_DCA_STRATEGY;
  } catch {
    return DEFAULT_DCA_STRATEGY;
  }
}

function loadStoredActiveTab() {
  if (typeof window === "undefined") return "risk";
  const tab = window.localStorage.getItem(ACTIVE_TAB_STORAGE_KEY);
  const migrations = { overview: "risk", metrics: "method", dca: "scenarios" };
  const resolved = migrations[tab] ?? tab;
  return TAB_KEYS.includes(resolved) ? resolved : "risk";
}

function statusTone(status) {
  if (status === "pass") return "green";
  if (status === "fail" || status === "blocked") return "red";
  if (status === "warn") return "amber";
  return "blue";
}

function shortHash(value) {
  if (!value) return "n/a";
  return String(value).slice(0, 10);
}

function EvidenceBar({ label, value, total, tone = "amber" }) {
  const safeTotal = Number(total) > 0 ? Number(total) : 0;
  const safeValue = Number(value) > 0 ? Number(value) : 0;
  const width = safeTotal > 0 ? Math.max(1, Math.min(100, (safeValue / safeTotal) * 100)) : 0;
  return (
    <div className="bb-evidence-bar">
      <div className="bb-evidence-bar__row">
        <span>{label}</span>
        <span>
          {integerLabel(safeValue)} / {integerLabel(safeTotal)}
        </span>
      </div>
      <div className="bb-evidence-bar__track" aria-hidden="true">
        <span className={`bb-evidence-bar__fill bb-evidence-bar__fill--${tone}`} style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

function EvidencePanel({ evaluationSummary }) {
  if (!evaluationSummary) {
    return (
      <section className="bb-panel bb-panel--focus" aria-label="Evidence">
        <div className="bb-panel__head">
          <h2 className="bb-panel__title bb-panel__title--solo">Evaluation Evidence</h2>
        </div>
        <p className="bb-empty">No Phase 2 evaluation summary artifact is available.</p>
      </section>
    );
  }

  const claim = evaluationSummary.claim_state ?? {};
  const sourceRun = evaluationSummary.source_run ?? {};
  const robustness = evaluationSummary.robustness ?? {};
  const validity = evaluationSummary.validity ?? {};
  const strength = evaluationSummary.strength ?? {};
  const practical = evaluationSummary.practical ?? {};
  const blockers = Array.isArray(evaluationSummary.blocking_warnings) ? evaluationSummary.blocking_warnings : [];
  const warnings = Array.isArray(evaluationSummary.top_warnings) ? evaluationSummary.top_warnings : [];
  const groups = Array.isArray(evaluationSummary.test_groups) ? evaluationSummary.test_groups : [];
  const bestRows = Array.isArray(practical.best_rows) ? practical.best_rows : [];
  const blocked = claim.status === "blocked" || sourceRun.status === "fail";

  return (
    <section aria-label="Evidence">
      <section className={`bb-evidence-hero${blocked ? " bb-evidence-hero--blocked" : ""}`}>
        <div>
          <p className="bb-panel__eyebrow">Phase 3 Evidence Dashboard</p>
          <h2 className="bb-evidence-hero__title">{claim.headline ?? "Evaluation evidence"}</h2>
          <p className="bb-evidence-hero__text">
            {claim.interpretation ??
              "This view summarizes the latest metric evaluation run and its claim gates."}
          </p>
        </div>
        <div className="bb-evidence-hero__meta">
          <span>RUN {sourceRun.run_id ?? "n/a"}</span>
          <span>PROFILE {sourceRun.profile ?? "n/a"}</span>
          <span>STATUS {(sourceRun.status ?? "unknown").toUpperCase()}</span>
          <span>COMMIT {shortHash(sourceRun.git_commit)}</span>
        </div>
      </section>

      <div className="bb-card-grid bb-card-grid--focus">
        <CountCard label="Tests Passed" value={claim.pass_count} tone="green" highlight />
        <CountCard label="Warnings" value={claim.warn_count} tone="amber" highlight />
        <CountCard label="Tests Failed" value={claim.fail_count} tone="red" highlight />
        <CountCard label="Blocking Warnings" value={claim.blocking_warning_count} tone="red" highlight />
        <CountCard label="High Severity" value={claim.high_warning_count} tone="red" highlight />
      </div>

      <div className="bb-evidence-layout">
        <section className="bb-panel">
          <div className="bb-panel__head">
            <h2 className="bb-panel__title bb-panel__title--solo">Claim Blockers</h2>
          </div>
          <div className="bb-warning-list">
            {blockers.length > 0 ? (
              blockers.map((warning) => (
                <article className="bb-warning-item" key={`${warning.test_id}-${warning.code}-${warning.message}`}>
                  <p className="bb-warning-item__code">{warning.code}</p>
                  <p className="bb-warning-item__message">{warning.message}</p>
                  <p className="bb-warning-item__meta">
                    {warning.test_id} / {String(warning.severity || "unknown").toUpperCase()}
                  </p>
                </article>
              ))
            ) : (
              <p className="bb-empty">No dashboard-blocking warnings were emitted.</p>
            )}
          </div>
        </section>

        <section className="bb-panel">
          <div className="bb-panel__head">
            <h2 className="bb-panel__title bb-panel__title--solo">Robustness Funnel</h2>
          </div>
          <div className="bb-evidence-bars">
            <EvidenceBar label="Walk-forward rows" value={robustness.walkforward_rows} total={robustness.walkforward_rows} tone="blue" />
            <EvidenceBar label="Survive circular-shift null" value={robustness.survives_circular_shift_null} total={robustness.walkforward_rows} tone="amber" />
            <EvidenceBar label="Pass AUC FDR" value={robustness.passes_fdr_auc} total={robustness.walkforward_rows} tone="amber" />
            <EvidenceBar label="Pass event concentration" value={robustness.passes_event_concentration} total={robustness.walkforward_rows} tone="amber" />
            <EvidenceBar label="Pass initial gates" value={robustness.initial_robust_rows} total={robustness.walkforward_rows} tone={robustness.initial_robust_rows > 0 ? "green" : "red"} />
          </div>
          <p className="bb-evidence-note">
            The current standard run has {integerLabel(robustness.initial_robust_rows)} rows passing the initial robustness gates.
          </p>
        </section>
      </div>

      <div className="bb-panel-grid bb-panel-grid--two bb-evidence-spaced">
        <section className="bb-panel">
          <div className="bb-panel__head">
            <h2 className="bb-panel__title bb-panel__title--solo">Validity And Strength</h2>
          </div>
          <table className="bb-table">
            <tbody>
              <tr>
                <th>Future-shift failed labels</th>
                <td>{integerLabel(validity.future_shift_material_advantage_label_rows)} rows</td>
              </tr>
              <tr>
                <th>Future-shift probe rows</th>
                <td>{integerLabel(validity.future_shift_material_advantage_probe_rows)} / {integerLabel(validity.future_shift_probe_rows)}</td>
              </tr>
              <tr>
                <th>Label cluster pass rows</th>
                <td>{integerLabel(validity.label_cluster_pass_rows)} / {integerLabel(validity.label_rows)}</td>
              </tr>
              <tr>
                <th>Degraded-data pass rows</th>
                <td>{integerLabel(strength.degraded_pass_rows)} / {integerLabel(strength.degraded_rows)}</td>
              </tr>
              <tr>
                <th>Rolling stability pass rows</th>
                <td>{integerLabel(strength.rolling_stability_pass_rows)} / {integerLabel(strength.rolling_rows)}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section className="bb-panel">
          <div className="bb-panel__head">
            <h2 className="bb-panel__title bb-panel__title--solo">Practical Use</h2>
          </div>
          <table className="bb-table">
            <tbody>
              <tr>
                <th>Metric-policy rows</th>
                <td>{integerLabel(practical.metric_policy_rows)}</td>
              </tr>
              <tr>
                <th>Beat buy-and-hold after costs</th>
                <td>{integerLabel(practical.metric_policy_beats_buy_hold_rows)}</td>
              </tr>
              <tr>
                <th>Risk-weighted DCA rows</th>
                <td>{integerLabel(practical.risk_weighted_dca_rows)}</td>
              </tr>
              <tr>
                <th>Beat fixed DCA</th>
                <td>{integerLabel(practical.risk_weighted_dca_beats_fixed_rows)}</td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>

      <section className="bb-panel bb-panel--focus">
        <div className="bb-panel__head">
          <h2 className="bb-panel__title bb-panel__title--solo">Test Family Matrix</h2>
        </div>
        <table className="bb-table bb-table--evidence">
          <thead>
            <tr>
              <th>Family</th>
              <th>Pass</th>
              <th>Warn</th>
              <th>Fail</th>
              <th>Representative Tests</th>
            </tr>
          </thead>
          <tbody>
            {groups.map((group) => (
              <tr key={group.family}>
                <td>{group.family}</td>
                <td className="bb-table__status bb-table__status--green">{integerLabel(group.pass)}</td>
                <td className="bb-table__status bb-table__status--amber">{integerLabel(group.warn)}</td>
                <td className="bb-table__status bb-table__status--red">{integerLabel(group.fail)}</td>
                <td>
                  {(group.tests ?? []).slice(0, 3).map((test) => (
                    <span key={test.test_id} className={`bb-test-chip bb-test-chip--${statusTone(test.status)}`}>
                      {test.test_id}
                    </span>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="bb-panel bb-panel--focus">
        <div className="bb-panel__head">
          <h2 className="bb-panel__title bb-panel__title--solo">Best Practical Rows Still Do Not Clear Claims</h2>
        </div>
        <table className="bb-table bb-table--evidence">
          <thead>
            <tr>
              <th>Signal</th>
              <th>Strategy</th>
              <th>Cost</th>
              <th>CAGR</th>
              <th>Vs Buy/Hold</th>
              <th>Max DD</th>
            </tr>
          </thead>
          <tbody>
            {bestRows.slice(0, 6).map((row, idx) => (
              <tr key={`${row.signal}-${row.strategy}-${row.cost_bps}-${idx}`}>
                <td>{row.signal ?? "n/a"}</td>
                <td>{row.strategy ?? "n/a"}</td>
                <td>{integerLabel(row.cost_bps)} bps</td>
                <td>{percentLabel(row.cagr)}</td>
                <td className={Number(row.cagr_delta_vs_buy_hold) >= 0 ? "bb-table__status--green" : "bb-table__status--red"}>
                  {percentLabel(row.cagr_delta_vs_buy_hold)}
                </td>
                <td>{percentLabel(row.max_drawdown)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="bb-evidence-note">
          These are sorted by relative CAGR. They are shown for inspection, not as promoted strategies.
        </p>
      </section>

      <section className="bb-panel bb-panel--focus">
        <div className="bb-panel__head">
          <h2 className="bb-panel__title bb-panel__title--solo">Top Evaluation Warnings</h2>
        </div>
        <table className="bb-table bb-table--evidence">
          <thead>
            <tr>
              <th>Severity</th>
              <th>Test</th>
              <th>Code</th>
              <th>Message</th>
            </tr>
          </thead>
          <tbody>
            {warnings.map((warning) => (
              <tr key={`${warning.test_id}-${warning.code}-${warning.message}`}>
                <td className={`bb-table__status--${statusTone(warning.severity === "high" ? "fail" : warning.severity === "medium" ? "warn" : "pass")}`}>
                  {String(warning.severity || "unknown").toUpperCase()}
                </td>
                <td>{warning.test_id ?? "n/a"}</td>
                <td>{warning.code ?? "n/a"}</td>
                <td>{warning.message ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </section>
  );
}

function StrategyField({ label, value, min = 0, max, step, onChange }) {
  return (
    <label className="bb-dca-field">
      <span>{label}</span>
      <input
        className="bb-dca-input"
        type="number"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function AlertsSignupPanel({ strategyBuy, strategySell }) {
  const [email, setEmail] = useState("");
  const [buyInput, setBuyInput] = useState(String(strategyBuy));
  const [sellInput, setSellInput] = useState(String(strategySell));
  const [website, setWebsite] = useState("");
  const [status, setStatus] = useState("idle");
  const [message, setMessage] = useState("");

  function matchStrategy() {
    setBuyInput(String(strategyBuy));
    setSellInput(String(strategySell));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const buy = Number(buyInput);
    const sell = Number(sellInput);
    if (!EMAIL_PATTERN.test(email.trim())) {
      setStatus("error");
      setMessage("Enter a valid email address.");
      return;
    }
    if (!Number.isFinite(buy) || !Number.isFinite(sell) || buy < 0 || sell > 1 || buy >= sell) {
      setStatus("error");
      setMessage("Thresholds must satisfy 0 ≤ accumulate < sell ≤ 1.");
      return;
    }
    setStatus("submitting");
    setMessage("");
    try {
      const response = await fetch("/api/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(),
          buyThreshold: buy,
          sellThreshold: sell,
          website,
        }),
      });
      const data = await response.json().catch(() => null);
      if (response.ok && data?.ok) {
        setStatus("success");
        setMessage(data.message ?? "Check your inbox to confirm your subscription.");
      } else {
        setStatus("error");
        setMessage(data?.error ?? "Subscription failed. Try again later.");
      }
    } catch {
      setStatus("error");
      setMessage("Network error. Try again later.");
    }
  }

  return (
    <section className="bb-panel">
      <div className="bb-panel__head">
        <h2 className="bb-panel__title bb-panel__title--solo">Email Alerts</h2>
        <button type="button" className="bb-button" onClick={matchStrategy}>
          Match Strategy
        </button>
      </div>
      <form className="bb-alerts-form" onSubmit={handleSubmit}>
        <label className="bb-dca-field bb-alerts-email">
          <span>Email</span>
          <input
            className="bb-dca-input"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>
        <StrategyField
          label="Accumulate At/Below"
          value={buyInput}
          max={1}
          step="0.01"
          onChange={setBuyInput}
        />
        <StrategyField
          label="Sell At/Above"
          value={sellInput}
          max={1}
          step="0.01"
          onChange={setSellInput}
        />
        <input
          className="bb-alerts-honeypot"
          type="text"
          name="website"
          tabIndex={-1}
          autoComplete="off"
          aria-hidden="true"
          value={website}
          onChange={(event) => setWebsite(event.target.value)}
        />
        <button type="submit" className="bb-button bb-alerts-submit" disabled={status === "submitting"}>
          {status === "submitting" ? "Subscribing…" : "Subscribe"}
        </button>
      </form>
      {message && (
        <p className={`bb-alerts-status bb-alerts-status--${status}`} role="status">
          {message}
        </p>
      )}
      <p className="bb-dca-note">
        One email when the aggregate DCA risk enters your accumulate or sell zone, checked once per
        day after the data refresh. Confirmation required; every email includes an unsubscribe link.
        Signal only &mdash; nothing here handles money.
      </p>
    </section>
  );
}

function RiskPanel({ historyCore, setActiveTab }) {
  const chartRef = useRef(null);
  const [priceScaleType, setPriceScaleType] = useState("logarithmic");
  const dcaSeries = useMemo(() => buildDcaRiskSeries(historyCore), [historyCore]);
  const btcSeries = useMemo(() => chartData(historyCore, "btc_price"), [historyCore]);
  const btcValues = useMemo(
    () => alignOverlayValues(dcaSeries.labels, btcSeries),
    [dcaSeries.labels, btcSeries],
  );
  const latestIndex = dcaSeries.labels.length - 1;
  const latestCoverage = latestIndex >= 0 ? Number(dcaSeries.coverageValues?.[latestIndex]) : 0;
  const isDegraded = latestCoverage < 0.75 || !Number.isFinite(Number(dcaSeries.values[latestIndex]));
  const latestRisk = !isDegraded && latestIndex >= 0 ? Number(dcaSeries.values[latestIndex]) : null;
  const latestDate = latestIndex >= 0 ? dcaSeries.labels[latestIndex] : null;
  const action = dcaActionForRisk(latestRisk, DEFAULT_DCA_STRATEGY);
  const hasBtcData = btcValues.some((value) => value !== null);
  const tone = action.side === "buy" ? "green" : action.side === "sell" ? "red" : "amber";
  const zoneLabel = isDegraded ? "DCA RISK UNAVAILABLE" : action.side === "buy" ? "LOW-RISK HISTORICAL ALIGNMENT" : action.side === "sell" ? "HIGH-RISK HISTORICAL ALIGNMENT" : "MID-RANGE HISTORICAL ALIGNMENT";
  const componentRows = dcaSeries.components.map((component) => ({
    ...component,
    latestValue: latestIndex >= 0 ? component.values[latestIndex] : null,
  }));

  const chartPayload = useMemo(
    () => ({
      labels: dcaSeries.labels,
      datasets: [
        {
          label: "DCA Risk Indicator",
          data: dcaSeries.values,
          borderColor: COLORS.amber,
          borderWidth: 2.4,
          pointRadius: 0,
          fill: true,
          backgroundColor: "#f0a5001f",
          tension: 0.15,
          yAxisID: "y",
        },
        {
          label: "Default Accumulation Threshold",
          data: dcaSeries.labels.map(() => DEFAULT_DCA_STRATEGY.buyStartRisk),
          borderColor: COLORS.green,
          borderDash: [5, 5],
          borderWidth: 1.1,
          pointRadius: 0,
          yAxisID: "y",
        },
        {
          label: "Default De-risking Threshold",
          data: dcaSeries.labels.map(() => DEFAULT_DCA_STRATEGY.sellStartRisk),
          borderColor: COLORS.red,
          borderDash: [5, 5],
          borderWidth: 1.1,
          pointRadius: 0,
          yAxisID: "y",
        },
        ...(hasBtcData
          ? [{
              label: "BTC Price",
              data: btcValues,
              borderColor: "#8b8473",
              borderWidth: 1.2,
              pointRadius: 0,
              fill: false,
              tension: 0.12,
              yAxisID: "yPrice",
            }]
          : []),
      ],
    }),
    [dcaSeries.labels, dcaSeries.values, hasBtcData, btcValues],
  );
  const options = useMemo(
    () => makeChartOptions({
      numLabels: dcaSeries.labels.length,
      hasPrice: hasBtcData,
      priceScaleType,
      accentColor: COLORS.amber,
    }),
    [dcaSeries.labels.length, hasBtcData, priceScaleType],
  );

  return (
    <section aria-label="DCA Risk">
      <div className="bb-risk-hero">
        <div className="bb-risk-hero__reading">
          <p className="bb-risk-hero__eyebrow">DCA RISK / {latestDate ?? "NO CURRENT RELEASE"}</p>
          <p className={`bb-risk-hero__value bb-card__value--${tone}`}>{valueLabel(latestRisk, 3)}</p>
          <p className={`bb-risk-hero__zone bb-card__value--${tone}`}>{zoneLabel}</p>
        </div>
        <div className="bb-risk-hero__copy">
          <p>
            A descriptive long-horizon index of how current conditions align with historically
            lower- and higher-risk cycle regimes. It is not a validated forecast or trading signal.
          </p>
          <div className="bb-risk-hero__actions">
            <button type="button" className="bb-button bb-button--primary" disabled={isDegraded} onClick={() => setActiveTab("scenarios")}>
              Test a strategy
            </button>
            <button type="button" className="bb-button" onClick={() => setActiveTab("method")}>
              See how it is built
            </button>
          </div>
        </div>
      </div>

      <section className="bb-panel bb-panel--focus">
        <div className="bb-panel__head">
          <h2 className="bb-panel__title bb-panel__title--solo">DCA Risk History</h2>
          <div className="bb-panel__actions">
            {hasBtcData && (
              <select className="bb-select bb-select--compact" value={priceScaleType} onChange={(event) => setPriceScaleType(event.target.value)}>
                <option value="logarithmic">LOG</option>
                <option value="linear">LINEAR</option>
              </select>
            )}
            <button type="button" className="bb-button" onClick={() => chartRef.current?.resetZoom?.()}>Reset Zoom</button>
          </div>
        </div>
        <div className="bb-chart-wrap bb-chart-wrap--focus" data-testid="risk-chart">
          {dcaSeries.labels.length > 0 ? (
            <Line ref={chartRef} data={chartPayload} options={options} plugins={[hoverGuidePlugin]} />
          ) : (
            <p className="bb-empty">No DCA Risk data available.</p>
          )}
        </div>
        <p className="bb-dca-note">
          Lower readings indicate historically more accumulation-like conditions; higher readings
          indicate increasingly heated conditions. Thresholds are policy choices, not guarantees.
        </p>
      </section>

      <div className="bb-risk-components">
        <div className="bb-risk-components__head">
          <div>
            <p className="bb-section-title">What is driving the reading</p>
            <p className="bb-dca-note">Supporting components shown in the same low-to-high risk direction.</p>
          </div>
          <button type="button" className="bb-link" onClick={() => setActiveTab("method")}>Full methodology →</button>
        </div>
        <div className="bb-card-grid bb-card-grid--dca">
          {componentRows.map((component) => (
            <MetricCard key={component.key} label={component.label} value={component.latestValue} tone="blue" />
          ))}
        </div>
      </div>

      <AlertsSignupPanel
        strategyBuy={DEFAULT_DCA_STRATEGY.buyStartRisk}
        strategySell={DEFAULT_DCA_STRATEGY.sellStartRisk}
      />
    </section>
  );
}

function ComparisonScenarioPanel({ historyCore }) {
  const chartRef = useRef(null);
  const [strategyInput, setStrategyInput] = useState(loadStoredDcaStrategy);
  const dcaSeries = useMemo(() => buildDcaRiskSeries(historyCore), [historyCore]);
  const btcSeries = useMemo(() => chartData(historyCore, "btc_price"), [historyCore]);
  const btcValues = useMemo(
    () => alignOverlayValues(dcaSeries.labels, btcSeries),
    [dcaSeries.labels, btcSeries],
  );
  const simulationInput = useMemo(
    () => ({ ...dcaSeries, priceValues: btcValues }),
    [dcaSeries, btcValues],
  );
  const comparison = useMemo(
    () => simulateDcaComparison(simulationInput, strategyInput),
    [simulationInput, strategyInput],
  );
  const strategy = comparison.strategy;
  const recentRows = comparison.rows.slice(-12).reverse();
  const latestIndex = dcaSeries.labels.length - 1;
  const isDcaDegraded = latestIndex < 0
    || Number(dcaSeries.coverageValues?.[latestIndex]) < 0.75
    || !Number.isFinite(Number(dcaSeries.values[latestIndex]));

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(DCA_STRATEGY_STORAGE_KEY, JSON.stringify(strategyInput));
  }, [strategyInput]);

  function updateStrategy(key, value) {
    setStrategyInput((previous) => ({ ...previous, [key]: value }));
  }

  const chartPayload = useMemo(
    () => ({
      labels: comparison.rows.map((row) => row.date),
      datasets: [
        {
          label: "Fixed DCA value",
          data: comparison.rows.map((row) => row.fixedValue),
          borderColor: COLORS.blue,
          borderWidth: 1.7,
          pointRadius: 0,
          tension: 0.12,
          yAxisID: "y",
        },
        {
          label: "DCA Risk strategy value",
          data: comparison.rows.map((row) => row.dynamicValue),
          borderColor: COLORS.amber,
          backgroundColor: "#f0a50018",
          borderWidth: 2.3,
          pointRadius: 0,
          fill: true,
          tension: 0.12,
          yAxisID: "y",
        },
      ],
    }),
    [comparison.rows],
  );
  const options = useMemo(
    () => makeChartOptions({
      numLabels: comparison.rows.length,
      hasPrice: false,
      priceScaleType: "linear",
      accentColor: COLORS.amber,
      yAutoScale: true,
    }),
    [comparison.rows.length],
  );

  if (isDcaDegraded) {
    return (
      <section aria-label="Scenarios" className="bb-panel bb-panel--focus">
        <h2 className="bb-panel__title bb-panel__title--solo">Scenarios unavailable</h2>
        <p className="bb-dca-warning">
          The latest DCA Risk reading does not meet the 75% component-coverage requirement.
          Scenario actions remain disabled until coverage recovers.
        </p>
      </section>
    );
  }

  return (
    <section aria-label="Scenarios">
      <div className="bb-scenario-intro">
        <div>
          <p className="bb-risk-hero__eyebrow">ILLUSTRATIVE COMPARISON</p>
          <h2>Same deposits. Different allocation policy.</h2>
        </div>
        <p>
          Both ledgers receive the same external cashflow each month. Fixed DCA invests it immediately;
          the dynamic ledger uses the prior month&apos;s DCA Risk reading, so no observation trades itself.
        </p>
      </div>

      <section className="bb-panel bb-scenario-controls">
        <div className="bb-panel__head">
          <h3 className="bb-panel__title bb-panel__title--solo">Scenario assumptions</h3>
          <button type="button" className="bb-button" onClick={() => setStrategyInput(DEFAULT_DCA_STRATEGY)}>Reset</button>
        </div>
        <div className="bb-dca-controls bb-dca-controls--scenario">
          <label className="bb-dca-field">
            <span>Start Date</span>
            <input
              className="bb-dca-input"
              type="date"
              value={strategy.startDate}
              min={dcaSeries.labels[0] ?? undefined}
              max={dcaSeries.labels.at(-1) ?? undefined}
              onChange={(event) => updateStrategy("startDate", event.target.value)}
            />
          </label>
          <StrategyField label="Monthly Deposit" value={strategy.monthlyContribution} step="25" onChange={(value) => updateStrategy("monthlyContribution", value)} />
          <StrategyField label="Accumulate At / Below" value={strategyInput.buyStartRisk} max={1} step="0.01" onChange={(value) => updateStrategy("buyStartRisk", value)} />
          <StrategyField label="De-risk At / Above" value={strategyInput.sellStartRisk} max={1} step="0.01" onChange={(value) => updateStrategy("sellStartRisk", value)} />
        </div>
        {comparison.warnings.length > 0 ? <p className="bb-dca-warning">{comparison.warnings.join(" ")}</p> : null}
        <p className="bb-dca-note">
          Monthly close execution · 0.20% fee + slippage · up to 3× allocation in low-risk months ·
          up to 35% de-risking in high-risk months · 10% cash buffer. Results are retrospective and illustrative,
          not a forecast or investment advice.
        </p>
      </section>

      <div className="bb-scenario-results">
        {[
          ["Fixed DCA", comparison.fixed, "blue"],
          ["DCA Risk strategy", comparison.dynamic, "amber"],
        ].map(([label, result, tone]) => (
          <article className={`bb-scenario-result bb-scenario-result--${tone}`} key={label}>
            <p className="bb-card__label">{label}</p>
            <p className={`bb-scenario-result__value bb-card__value--${tone}`}>{formatMoney(result.endingValue)}</p>
            <dl>
              <div><dt>Deposited</dt><dd>{formatMoney(result.totalContributed)}</dd></div>
              <div><dt>Gain / loss</dt><dd>{formatMoney(result.gain)}</dd></div>
              <div><dt>Money-weighted</dt><dd>{percentLabel(result.moneyWeightedReturn)}</dd></div>
              <div><dt>Time-weighted</dt><dd>{percentLabel(result.timeWeightedReturn)}</dd></div>
            </dl>
          </article>
        ))}
      </div>

      <section className="bb-panel bb-panel--focus">
        <div className="bb-panel__head">
          <h3 className="bb-panel__title bb-panel__title--solo">Illustrative account value</h3>
          <button type="button" className="bb-button" onClick={() => chartRef.current?.resetZoom?.()}>Reset Zoom</button>
        </div>
        <div className="bb-chart-wrap bb-chart-wrap--focus" data-testid="scenario-chart">
          {comparison.rows.length > 0
            ? <Line ref={chartRef} data={chartPayload} options={options} plugins={[hoverGuidePlugin]} />
            : <p className="bb-empty">No price and DCA Risk overlap for this start date.</p>}
        </div>
      </section>

      <section className="bb-panel bb-panel--focus">
        <div className="bb-panel__head"><h3 className="bb-panel__title bb-panel__title--solo">Recent monthly executions</h3></div>
        <table className="bb-table bb-table--dca">
          <thead><tr><th>Date</th><th>Prior risk used</th><th>Equal deposit</th><th>Dynamic action</th><th>Fixed value</th><th>Dynamic value</th></tr></thead>
          <tbody>
            {recentRows.length > 0 ? recentRows.map((row) => (
              <tr key={row.date}>
                <td>{row.date}</td><td>{valueLabel(row.riskUsed, 3)}</td><td>{formatMoney(row.contribution)}</td>
                <td>{row.buyAmount > 0 ? `Buy ${formatMoney(row.buyAmount)}` : row.sellAmount > 0 ? `Sell ${formatMoney(row.sellAmount)}` : "Hold cash"}</td>
                <td>{formatMoney(row.fixedValue)}</td><td>{formatMoney(row.dynamicValue)}</td>
              </tr>
            )) : <tr><td colSpan="6">No monthly executions in the selected range.</td></tr>}
          </tbody>
        </table>
      </section>
    </section>
  );
}

const ABOUT_HEADLINE_KEYS = [
  "top_reversal_risk",
  "bottom_reversal_risk",
  "cycle_extension",
  "headline_attention",
  "cycle_regime",
];

function AboutEntry({ copy }) {
  return (
    <div className="bb-about__entry">
      <div className="bb-about__entry-rail">
        <div className="bb-about__entry-name">{copy.shortName}</div>
        {copy.oneLiner && <div className="bb-about__entry-tag">{copy.oneLiner}</div>}
      </div>
      <div className="bb-about__entry-body">
        <p className="bb-about__desc">{copy.description}</p>
        {copy.notMeaning && (
          <p className="bb-about__not">
            <span className="bb-about__not-label">Not</span> {copy.notMeaning}
          </p>
        )}
        <details className="bb-about__technical">
          <summary>Technical detail</summary>
          <table className="bb-table">
            <tbody>
              {copy.technicalRows.map((row) => (
                <tr key={row.label}>
                  <td>{row.label}</td>
                  <td>{row.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      </div>
    </div>
  );
}

function AboutPanel() {
  return (
    <section className="bb-about">
      <div className="bb-about__hero">
        <p className="bb-about__lede">
          A personal project exploring quantitative approaches to understanding Bitcoin market cycles.
        </p>
        <p className="bb-about__hero-body">
          The product's central output is the <strong>DCA Risk Indicator</strong>: a long-horizon
          accumulation and de-risking index, not a short-term trading signal or literal probability.
          Top and Bottom Reversal Risk, Cycle Extension, Signal Agreement, and the Cycle Frenzy Score
          explain its construction. Long-history results include retrospective reconstructions where
          historical source vintages are unavailable; prospectively frozen releases are tracked
          separately as their outcomes mature.
        </p>
      </div>

      <div className="bb-about__section">
        <div className="bb-about__section-head">
          <span className="bb-about__rule" />
          <h2 className="bb-about__section-title">Headline Indices</h2>
        </div>

        {ABOUT_HEADLINE_KEYS.map((key) => (
          <AboutEntry key={key} copy={METRIC_COPY[key]} />
        ))}

        <div className="bb-about__methodology">
          <div className="bb-about__methodology-eyebrow">Scoring methodology</div>
          <ol className="bb-about__methodology-list">
            {METRIC_COPY.scoring.steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </div>
      </div>

      <div className="bb-about__section">
        <div className="bb-about__section-head">
          <span className="bb-about__rule" />
          <h2 className="bb-about__section-title">Input Metrics</h2>
        </div>

        {CURATED_METRICS.map((m) => (
          <AboutEntry key={m.key} copy={METRIC_COPY[m.copyKey]} />
        ))}
        <AboutEntry copy={METRIC_COPY.mvrv_implied_profitability_proxy} />
      </div>
    </section>
  );
}

export default function App() {
  const [status, setStatus] = useState("loading");
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState(loadStoredActiveTab);

  useEffect(() => {
    let active = true;
    loadDashboardData()
      .then((data) => {
        if (!active) return;
        setPayload(data);
        setStatus("ready");
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Unknown data load error");
        setStatus("error");
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(ACTIVE_TAB_STORAGE_KEY, activeTab);
  }, [activeTab]);

  if (status === "loading") {
    return (
      <div className="bb-app">
        <p className="bb-status">
          LOADING<span className="bb-blink">_</span>
        </p>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="bb-app">
        <p className="bb-status bb-status--error">ERROR: {error}</p>
      </div>
    );
  }

  const { latestSnapshot, historyCore, metricBtc, manifest, diagnostics, evaluationSummary } = payload;

  return (
    <div className="bb-app">
      <StatusTicker
        manifest={manifest}
        latestSnapshot={latestSnapshot}
        diagnostics={diagnostics}
        evaluationSummary={evaluationSummary}
      />

      <main className="bb-main">
        <div className="bb-tabs" role="tablist" aria-label="Dashboard Views">
          {[
            { key: "risk", label: "DCA Risk" },
            { key: "method", label: "Method" },
            { key: "scenarios", label: "Scenarios" },
            { key: "evidence", label: "Evidence" },
            { key: "about", label: "About" },
          ].map(({ key, label }) => (
            <button
              key={key}
              type="button"
              className={`bb-tab${activeTab === key ? " bb-tab--active" : ""}`}
              onClick={() => setActiveTab(key)}
              role="tab"
              aria-selected={activeTab === key}
            >
              {label}
            </button>
          ))}
        </div>

        {activeTab === "risk" && <RiskPanel historyCore={historyCore} setActiveTab={setActiveTab} />}

        {activeTab === "method" && (
          <section aria-label="Method">
            <div className="bb-card-grid bb-card-grid--focus">
              <MetricCard label="Top Reversal Risk" value={latestSnapshot.top_reversal_risk} tone="red" highlight />
              <MetricCard label="Bottom Reversal Risk" value={latestSnapshot.bottom_reversal_risk} tone="green" highlight />
              <MetricCard label="Cycle Extension" value={latestSnapshot.cycle_extension_score} tone="amber" highlight />
              <MetricCard label="Signal Agreement" value={latestSnapshot.attention_score} tone="blue" highlight />
              <MetricCard
                label="Cycle Frenzy Score"
                value={latestSnapshot.cycle_model?.frenzy_score ?? latestSnapshot.cycle_frenzy_score}
                tone="violet"
                highlight
              />
            </div>
            <OverviewPanel historyCore={historyCore} setActiveTab={setActiveTab} />
            <MetricsPanel metricBtc={metricBtc} historyCore={historyCore} setActiveTab={setActiveTab} />
          </section>
        )}

        {activeTab === "evidence" && <EvidencePanel evaluationSummary={evaluationSummary} />}

        {activeTab === "scenarios" && <ComparisonScenarioPanel historyCore={historyCore} />}

        {activeTab === "about" && (
          <section aria-label="About">
            <AboutPanel />
          </section>
        )}
      </main>

      <footer className="bb-footer">
        Personal project &middot; Code written with a lot of support from AI &middot; Not investment advice.
      </footer>
    </div>
  );
}
