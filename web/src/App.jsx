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
  loadDashboardData,
  simulateDcaStrategy,
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
const DAY_OPTIONS = [
  ["monday", "Monday"],
  ["tuesday", "Tuesday"],
  ["wednesday", "Wednesday"],
  ["thursday", "Thursday"],
  ["friday", "Friday"],
  ["saturday", "Saturday"],
  ["sunday", "Sunday"],
];

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

function formatUnits(value) {
  const num = Number(value);
  return Number.isFinite(num) ? num.toFixed(6) : "n/a";
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

function StatusTicker({ manifest, latestSnapshot, diagnostics }) {
  const validation = validationState(diagnostics);
  const sourceIssues = criticalSourceIssues(diagnostics);
  const generatedAt = manifest?.generated_at ?? latestSnapshot?.generated_at;
  const scoreDate = latestSnapshot?.date ?? "n/a";
  const isFailing = validation.passed === false || sourceIssues.length > 0;
  const statusLabel = validation.passed === null ? "UNVERIFIED" : isFailing ? "VALIDATION FAIL" : "VALIDATED";

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
        label: "Cycle Regime Index",
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
    { key: "cycle", label: "Cycle Regime Index", color: COLORS.violet },
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
          primary signals here — calibrated, probability-like estimates of top-side and bottom-side
          reversal conditions. <strong>Cycle Extension</strong> measures how stretched price is
          versus long-run moving averages. <strong>Signal Agreement</strong> measures how broadly
          the underlying inputs agree with each other (high = many inputs pointing the same way; not
          a directional buy/sell). The <strong>Cycle Regime Index (CRI)</strong> is a slow-moving
          estimate of where the market sits within the multi-year cycle — near 0 looks historically
          accumulation-like, near 1 looks historically bubble-like.
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
  if (typeof window === "undefined") return "overview";
  const tab = window.localStorage.getItem(ACTIVE_TAB_STORAGE_KEY);
  return ["overview", "metrics", "dca", "about"].includes(tab) ? tab : "overview";
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

function DcaPanel({ historyCore }) {
  const chartRef = useRef(null);
  const [strategyInput, setStrategyInput] = useState(loadStoredDcaStrategy);
  const [priceScaleType, setPriceScaleType] = useState("logarithmic");

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
  const simulation = useMemo(() => simulateDcaStrategy(simulationInput, strategyInput), [simulationInput, strategyInput]);
  const strategy = simulation.strategy;
  const hasBtcData = btcValues.some((v) => v !== null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(DCA_STRATEGY_STORAGE_KEY, JSON.stringify(strategyInput));
  }, [strategyInput]);

  function updateStrategy(key, value) {
    setStrategyInput((prev) => ({ ...prev, [key]: value }));
  }

  function startToday() {
    const min = dcaSeries.labels[0];
    const max = dcaSeries.labels[dcaSeries.labels.length - 1];
    let today = new Date().toLocaleDateString("en-CA");
    if (max && today > max) today = max;
    if (min && today < min) today = min;
    updateStrategy("startDate", today);
  }

  const latest = simulation.latest;
  const latestIdx = latest ? dcaSeries.labels.indexOf(latest.date) : -1;
  const latestComponents = dcaSeries.components.map((component) => {
    const latestValue = latestIdx >= 0 ? component.values[latestIdx] : null;
    return { ...component, latestValue };
  });
  const recentSignals = simulation.signalRows.slice(-12).reverse();

  const chartPayload = useMemo(
    () => ({
      labels: dcaSeries.labels,
      datasets: [
        {
          label: "Aggregate DCA Risk",
          data: dcaSeries.values,
          borderColor: COLORS.amber,
          borderWidth: 2,
          pointRadius: 0,
          fill: true,
          backgroundColor: "#f0a5001f",
          tension: 0.15,
          yAxisID: "y",
        },
        {
          label: "Buy Threshold",
          data: dcaSeries.labels.map(() => strategy.buyStartRisk),
          borderColor: COLORS.green,
          borderDash: [5, 5],
          borderWidth: 1.2,
          pointRadius: 0,
          fill: false,
          yAxisID: "y",
        },
        {
          label: "Sell Threshold",
          data: dcaSeries.labels.map(() => strategy.sellStartRisk),
          borderColor: COLORS.red,
          borderDash: [5, 5],
          borderWidth: 1.2,
          pointRadius: 0,
          fill: false,
          yAxisID: "y",
        },
        ...(hasBtcData
          ? [
              {
                label: "BTC Price",
                data: btcValues,
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
    [dcaSeries.labels, dcaSeries.values, strategy.buyStartRisk, strategy.sellStartRisk, hasBtcData, btcValues],
  );

  const options = useMemo(
    () =>
      makeChartOptions({
        numLabels: dcaSeries.labels.length,
        hasPrice: hasBtcData,
        priceScaleType,
        accentColor: COLORS.amber,
      }),
    [dcaSeries.labels.length, hasBtcData, priceScaleType],
  );

  return (
    <section aria-label="DCA">
      <div className="bb-dca-layout">
        <section className="bb-panel">
          <div className="bb-panel__head">
            <h2 className="bb-panel__title bb-panel__title--solo">Strategy</h2>
            <button type="button" className="bb-button" onClick={() => setStrategyInput(DEFAULT_DCA_STRATEGY)}>
              Reset
            </button>
          </div>
          <div className="bb-dca-controls">
            <label className="bb-dca-field">
              <span className="bb-dca-field__label">
                Start Date
                <button type="button" className="bb-dca-today" onClick={startToday}>
                  Today
                </button>
              </span>
              <input
                className="bb-dca-input"
                type="date"
                value={strategy.startDate}
                min={dcaSeries.labels[0] ?? undefined}
                max={dcaSeries.labels[dcaSeries.labels.length - 1] ?? undefined}
                onChange={(event) => updateStrategy("startDate", event.target.value)}
              />
            </label>
            <label className="bb-dca-field">
              <span>Cadence</span>
              <select
                className="bb-dca-input"
                value={strategy.cadence}
                onChange={(event) => updateStrategy("cadence", event.target.value)}
              >
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
              </select>
            </label>
            <label className="bb-dca-field">
              <span>Day</span>
              <select
                className="bb-dca-input"
                value={strategy.dayOfWeek}
                onChange={(event) => updateStrategy("dayOfWeek", event.target.value)}
              >
                {DAY_OPTIONS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <StrategyField
              label="Buy Below"
              value={strategyInput.buyStartRisk}
              max={1}
              step="0.01"
              onChange={(value) => updateStrategy("buyStartRisk", value)}
            />
            <StrategyField
              label="Buy Step"
              value={strategyInput.buyStep}
              max={1}
              step="0.01"
              onChange={(value) => updateStrategy("buyStep", value)}
            />
            <StrategyField
              label="Buy Base"
              value={strategyInput.buyBaseAmount}
              step="1"
              onChange={(value) => updateStrategy("buyBaseAmount", value)}
            />
            <StrategyField
              label="Sell Above"
              value={strategyInput.sellStartRisk}
              max={1}
              step="0.01"
              onChange={(value) => updateStrategy("sellStartRisk", value)}
            />
            <StrategyField
              label="Sell Step"
              value={strategyInput.sellStep}
              max={1}
              step="0.01"
              onChange={(value) => updateStrategy("sellStep", value)}
            />
            <StrategyField
              label="Sell Base"
              value={strategyInput.sellBaseAmount}
              step="1"
              onChange={(value) => updateStrategy("sellBaseAmount", value)}
            />
          </div>
          {simulation.warnings.length > 0 && (
            <p className="bb-dca-warning">{simulation.warnings.join(" ")}</p>
          )}
        </section>

        <section className={`bb-dca-signal bb-dca-signal--${latest?.side ?? "hold"}`}>
          <p className="bb-dca-signal__label">Current Model Signal</p>
          <p className="bb-dca-signal__action">{latest?.label ?? "Hold"}</p>
          <p className="bb-dca-signal__risk">DCA Risk {valueLabel(latest?.risk, 3)}</p>
          <p className="bb-dca-signal__risk">Signal Date {latest?.date ?? "n/a"}</p>
          <p className="bb-dca-signal__amount">
            {latest?.side === "hold" ? `No allocation on ${latest?.date ?? "latest row"}` : `${formatMoney(latest?.amount)} notional`}
          </p>
        </section>
      </div>

      <div className="bb-card-grid bb-card-grid--dca">
        <MetricCard label="Aggregate DCA Risk" value={latest?.risk} tone="amber" highlight />
        {latestComponents.map((component) => (
          <MetricCard key={component.key} label={`${component.label} Component`} value={component.latestValue} tone="blue" />
        ))}
      </div>

      <div className="bb-card-grid bb-card-grid--account">
        <article className="bb-card">
          <p className="bb-card__label">Capital In</p>
          <p className="bb-card__value bb-card__value--green">{formatMoney(simulation.summary.buyTotal)}</p>
          <p className="bb-card__sub">{simulation.summary.buySignals} buy executions</p>
        </article>
        <article className="bb-card">
          <p className="bb-card__label">Sell Proceeds</p>
          <p className="bb-card__value bb-card__value--red">{formatMoney(simulation.summary.sellProceeds)}</p>
          <p className="bb-card__sub">{simulation.summary.sellSignals} sell executions</p>
        </article>
        <article className="bb-card">
          <p className="bb-card__label">Realized P/L</p>
          <p className={`bb-card__value bb-card__value--${simulation.summary.realizedPnl >= 0 ? "green" : "red"}`}>
            {formatMoney(simulation.summary.realizedPnl)}
          </p>
          <p className="bb-card__sub">after sold cost basis</p>
        </article>
        <article className="bb-card">
          <p className="bb-card__label">Remaining Position</p>
          <p className="bb-card__value bb-card__value--amber">{formatMoney(simulation.summary.positionValue)}</p>
          <p className="bb-card__sub">{formatUnits(simulation.summary.unitsHeld)} BTC</p>
        </article>
        <article className="bb-card">
          <p className="bb-card__label">Avg Entry</p>
          <p className="bb-card__value bb-card__value--amber">{formatMoney(simulation.summary.averageCostBasis)}</p>
          <p className="bb-card__sub">open position</p>
        </article>
      </div>

      <section className="bb-panel bb-panel--focus">
        <div className="bb-panel__head">
          <h2 className="bb-panel__title bb-panel__title--solo">Aggregate Risk</h2>
          <div className="bb-panel__actions">
            {hasBtcData && (
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
        <div className="bb-chart-wrap bb-chart-wrap--focus" data-testid="dca-chart">
          {dcaSeries.labels.length > 0 ? (
            <Line ref={chartRef} data={chartPayload} options={options} plugins={[hoverGuidePlugin]} />
          ) : (
            <p className="bb-empty">No DCA data available.</p>
          )}
        </div>
        <p className="bb-dca-note">
          Aggregate DCA Risk is an expanding historical normalization of top reversal risk, inverted
          bottom reversal risk, cycle extension, and cycle regime index. Lower values are buy-attractive;
          higher values are sell-risky. Component cards are already transformed into DCA-risk direction,
          so low component values are more attractive even when the original source metric is high-positive.
        </p>
      </section>

      <section className="bb-panel bb-panel--focus">
        <div className="bb-panel__head">
          <h2 className="bb-panel__title bb-panel__title--solo">Recent Strategy Signals</h2>
        </div>
        <table className="bb-table bb-table--dca">
          <thead>
            <tr>
              <th>Date</th>
              <th>Risk</th>
              <th>Action</th>
              <th>Amount</th>
              <th>BTC Held</th>
            </tr>
          </thead>
          <tbody>
            {recentSignals.length > 0 ? (
              recentSignals.map((row) => (
                <tr key={`${row.date}-${row.side}-${row.amount}`}>
                  <td>{row.date}</td>
                  <td>{valueLabel(row.risk, 3)}</td>
                  <td className={`bb-table__side bb-table__side--${row.side}`}>{row.label}</td>
                  <td>{formatMoney(row.amount)}</td>
                  <td>{formatUnits(row.unitsHeld)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="5">No buy or sell signals since the selected start date.</td>
              </tr>
            )}
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
          The primary operational signals are <strong>Top Reversal Risk</strong> and{" "}
          <strong>Bottom Reversal Risk</strong>. Cycle Extension, Signal Agreement, and the Cycle
          Regime Index sit alongside them as contextual regime descriptors. Every score on this
          dashboard is computed with point-in-time data — historical values are never recomputed
          with future information.
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

        {CURATED_METRICS.filter((m) => m.key !== "mvrv").map((m) => (
          <AboutEntry key={m.key} copy={METRIC_COPY[m.copyKey]} />
        ))}
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

  const { latestSnapshot, historyCore, metricBtc, manifest, diagnostics } = payload;

  return (
    <div className="bb-app">
      <StatusTicker manifest={manifest} latestSnapshot={latestSnapshot} diagnostics={diagnostics} />

      <main className="bb-main">
        <div className="bb-tabs" role="tablist" aria-label="Dashboard Views">
          {[
            { key: "overview", label: "Overview" },
            { key: "metrics", label: "Metrics" },
            { key: "dca", label: "DCA" },
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

        {activeTab === "overview" && (
          <section aria-label="Overview">
            <div className="bb-card-grid bb-card-grid--focus">
              <MetricCard label="Top Reversal Risk" value={latestSnapshot.top_reversal_risk} tone="red" highlight />
              <MetricCard label="Bottom Reversal Risk" value={latestSnapshot.bottom_reversal_risk} tone="green" highlight />
              <MetricCard label="Cycle Extension" value={latestSnapshot.cycle_extension_score} tone="amber" highlight />
              <MetricCard label="Signal Agreement" value={latestSnapshot.attention_score} tone="blue" highlight />
              <MetricCard
                label="Cycle Regime Index"
                value={latestSnapshot.cycle_model?.frenzy_score ?? latestSnapshot.cycle_frenzy_score}
                tone="violet"
                highlight
              />
            </div>
            <OverviewPanel historyCore={historyCore} setActiveTab={setActiveTab} />
          </section>
        )}

        {activeTab === "metrics" && (
          <section aria-label="Metrics">
            <MetricsPanel metricBtc={metricBtc} historyCore={historyCore} setActiveTab={setActiveTab} />
          </section>
        )}

        {activeTab === "dca" && <DcaPanel historyCore={historyCore} />}

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
