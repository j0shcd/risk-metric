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
  alertPreview,
  buildDcaRiskSeries,
  chartData,
  formatDateTick,
  formatPriceTick,
  loadDashboardData,
  loadMethodData,
  RISK_REGIONS,
  readingSummary,
  scoreLabel,
  valueLabel,
} from "./data";
import { CURATED_METRICS, METRIC_COPY } from "./copy";
import { DCA_EVIDENCE } from "./dcaEvidence";

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

// Chart colors mirror :root in styles.css.
const COLORS = {
  bg: "#0a0a0a",
  panel: "#111111",
  border: "#232323",
  borderDim: "#191919",
  text: "#cbc3ab",
  muted: "#938b7b",
  amber: "#f0a500",
  red: "#f05b5b",
  green: "#22cc55",
  blue: "#5ca2ff",
  violet: "#b58cff",
};

const FONT = "'IBM Plex Mono', 'Courier New', monospace";
const PRICE_FORMAT = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const LOW_MARK = RISK_REGIONS[0].max;
const HIGH_MARK = RISK_REGIONS[2].min;
const ACTIVE_TAB_STORAGE_KEY = "riskMetricActiveTab.v1";
const TABS = [
  { key: "today", label: "Today" },
  { key: "record", label: "Track record" },
  { key: "method", label: "Method" },
];
const TAB_KEYS = TABS.map((tab) => tab.key);

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

const DAY_FORMAT = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

function formatDay(value) {
  if (!value) return "an unknown date";
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return String(value);
  return DAY_FORMAT.format(date);
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
    ticks: { color: COLORS.muted, font: { family: FONT, size: 12 },
      ...(yAutoScale ? {} : { stepSize: 0.25, callback: (v) => scoreLabel(v) }),
    },
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
        ticks: {
          maxRotation: 0,
          autoSkip: true,
          maxTicksLimit: 8,
          autoSkipPadding: 24,
          callback: function (value) { return formatDateTick(this.getLabelForValue(value)); },
          color: COLORS.muted,
          font: { family: FONT, size: 12 },
        },
        grid: { color: COLORS.borderDim },
        border: { color: COLORS.border },
      },
      y: yScale,
      yPrice: {
        display: hasPrice,
        position: "right",
        type: priceScaleType,
        ticks: {
          callback: (v, _index, ticks) => formatPriceTick(
            v,
            priceScaleType === "logarithmic",
            ticks?.length ? ticks.at(-1).value / ticks[0].value : Infinity,
          ),
          autoSkip: true,
          maxTicksLimit: 6,
          autoSkipPadding: 12,
          color: COLORS.muted,
          font: { family: FONT, size: 12 },
        },
        grid: { drawOnChartArea: false },
        border: { color: COLORS.border },
      },
    },
    plugins: {
      legend: {
        display: showLegend,
        labels: { color: COLORS.text, font: { family: FONT, size: 12 }, boxWidth: 10 },
      },
      tooltip: {
        backgroundColor: "#090909f0",
        borderColor: COLORS.border,
        borderWidth: 1,
        titleColor: COLORS.text,
        bodyColor: COLORS.text,
        titleFont: { family: FONT, size: 12, weight: "600" },
        bodyFont: { family: FONT, size: 12 },
        callbacks: {
          title: (items) => (items.length ? `Date: ${items[0].label}` : ""),
          label: (item) =>
            item.dataset.yAxisID === "yPrice"
              ? `${item.dataset.label}: ${formatPrice(item.parsed.y)}`
              : `${item.dataset.label}: ${yAutoScale ? valueLabel(item.parsed.y, 4) : scoreLabel(item.parsed.y)}`,
        },
      },
      zoom: {
        limits: { x: { min: 0, max: Math.max(0, numLabels - 1) } },
        pan: { enabled: true, mode: "x" },
        zoom: {
          mode: "x",
          wheel: { enabled: true, modifierKey: "ctrl" },
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
      <p className={`bb-card__value bb-card__value--${tone}`}>{scoreLabel(value)}</p>
    </article>
  );
}

function daysSince(isoDate) {
  if (!isoDate) return null;
  const then = new Date(`${isoDate}T00:00:00Z`).getTime();
  if (Number.isNaN(then)) return null;
  return Math.floor((Date.now() - then) / 86400000);
}

function StatusTicker({ latestSnapshot, diagnostics }) {
  const validation = validationState(diagnostics);
  const sourceIssues = criticalSourceIssues(diagnostics);
  const scoreDate = latestSnapshot?.date ?? null;
  const age = daysSince(scoreDate);
  // The publication gate proves a release is internally consistent, not that it
  // is recent. A stalled daily job otherwise reads as healthy.
  const isStale = age !== null && age > 3;
  const isFailing = validation.passed === false || sourceIssues.length > 0 || isStale;

  const statusLabel = validation.passed === false || sourceIssues.length > 0
    ? "Data check needed"
    : isStale
      ? `${age} days behind`
      : "Updated daily";

  return (
    <header className="bb-topbar">
      <span className={`bb-live-dot${isFailing ? " bb-live-dot--fail" : ""}`} aria-hidden="true" />
      <span className={`bb-meta bb-meta--status${isFailing ? " bb-meta--fail" : ""}`}>{statusLabel}</span>
      <span className="bb-meta">Reading for {formatDay(scoreDate)}</span>
    </header>
  );
}

function OverviewPanel({ historyCore }) {
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
        label: "Looks like past peaks",
        data: topRiskSeries.values,
        borderColor: COLORS.red,
        borderWidth: 1.9,
        pointRadius: 0,
        fill: true,
        backgroundColor: "#f05b5b1f",
        tension: 0.16,
      });
    }
    if (visible.bottomRisk) {
      ds.push({
        label: "Looks like past bottoms",
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
        label: "Price stretch",
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
        label: "Signals agreeing",
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
        label: "Speculation and hype",
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
        label: "BTC price",
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
    { key: "topRisk", label: "Looks like past peaks", color: COLORS.red },
    { key: "bottomRisk", label: "Looks like past bottoms", color: COLORS.green },
    { key: "extension", label: "Price stretch", color: COLORS.amber },
    { key: "cycle", label: "Speculation and hype", color: COLORS.violet },
    { key: "attention", label: "Signals agreeing (context)", color: COLORS.blue },
  ];

  return (
    <section className="bb-panel bb-panel--focus">
      <div className="bb-panel__head">
        <h2 className="bb-panel__title bb-panel__title--solo">The four sub-scores over time</h2>
        <div className="bb-panel__actions">
          {showPrice && (
            <select
              aria-label="Price scale"
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
              className={`bb-legend__item${item.key === "attention" ? " bb-legend__item--context" : ""}${on ? "" : " bb-legend__item--off"}`}
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
          <span className="bb-legend__item bb-legend__item--static">
            <span className="bb-legend__swatch" style={{ background: "#8b8473" }} />
            <span className="bb-legend__label">BTC price</span>
          </span>
        )}
      </div>
      <div className="bb-chart-wrap bb-chart-wrap--focus" data-testid="overview-chart">
        {topRiskSeries.labels.length > 0 ? (
          <Line role="img" aria-label={`Sub-scores over time, shown: ${legendItems.filter((item) => visible[item.key]).map((item) => item.label).join(", ")}.`} ref={chartRef} data={chartPayload} options={options} plugins={[hoverGuidePlugin]} />
        ) : (
          <p className="bb-empty">No data available.</p>
        )}
      </div>
      <p className="bb-dca-note">
        Every line is rescaled 0 to 100 against its own history, so 100 means the most extreme reading ever seen. Series start in December 2014.
      </p>
    </section>
  );
}

function MetricsPanel({ metricBtc, historyCore }) {
  const availableMetrics = useMemo(
    () => CURATED_METRICS.filter((m) => chartData(metricBtc, m.btcColumn).values.some((v) => v !== null)),
    [metricBtc],
  );

  const defaultKey = availableMetrics.find((m) => m.key === "trend_extension")?.key ?? availableMetrics[0]?.key;
  const [selectedKey, setSelectedKey] = useState(defaultKey);
  const [priceScaleType, setPriceScaleType] = useState("logarithmic");
  const chartRef = useRef(null);

  const metric = availableMetrics.find((m) => m.key === selectedKey) ?? availableMetrics[0];
  const copy = metric ? METRIC_COPY[metric.copyKey] : null;

  useEffect(() => {
    chartRef.current?.resetZoom?.();
  }, [selectedKey]);

  const activeColumn = metric?.btcColumn;
  const priceColumn = "btc_price";
  const priceLabel = "BTC price";

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
            aria-label="Raw input"
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
        </div>
        <div className="bb-panel__actions">
          {hasPrice && (
            <label className="bb-checkbox">
              PRICE SCALE
              <select
                aria-label="Price scale"
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
          <Line role="img" aria-label={`${copy?.shortName ?? "Raw input"} with ${priceLabel}.`} ref={chartRef} data={chartPayload} options={options} plugins={[hoverGuidePlugin]} />
        ) : (
          <p className="bb-empty">No data available for this metric.</p>
        )}
      </div>
      <div className="bb-metric-desc">
        <p className="bb-metric-desc__text">{copy?.description ?? ""}</p>
      </div>
    </section>
  );
}

function loadStoredActiveTab() {
  if (typeof window === "undefined") return "today";
  let tab;
  try { tab = window.localStorage.getItem(ACTIVE_TAB_STORAGE_KEY); } catch { return "today"; }
  const migrations = {
    overview: "today",
    risk: "today",
    dca: "today",
    scenarios: "today",
    metrics: "method",
    about: "method",
    evidence: "record",
  };
  const resolved = migrations[tab] ?? tab;
  return TAB_KEYS.includes(resolved) ? resolved : "today";
}

function TrackRecordPanel() {
  return (
    <section className="bb-research" aria-labelledby="track-record-title">
      <header className="bb-research-hero">
        <div className="bb-research-hero__copy">
          <h1 id="track-record-title">{DCA_EVIDENCE.headline}</h1>
          <p>{DCA_EVIDENCE.summary}</p>
          <dl className="bb-research-meta">
            <div><dt>Last run</dt><dd>{formatDay(DCA_EVIDENCE.evaluatedAt)}</dd></div>
            <div><dt>History used</dt><dd>{DCA_EVIDENCE.dataWindow}</dd></div>
          </dl>
        </div>
        <aside className="bb-research-cannot">
          <h2>What it cannot do</h2>
          <ul>
            {DCA_EVIDENCE.cannotDo.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </aside>
      </header>

      <div className="bb-research-tests">
        {DCA_EVIDENCE.tests.map((test) => (
          <article className={`bb-research-test bb-research-test--${test.tone}`} key={test.id}>
            <div className="bb-research-test__head">
              <span className="bb-research-test__number">{test.number}</span>
              <span className={`bb-research-verdict bb-research-verdict--${test.tone}`}>{test.verdict}</span>
            </div>
            <h2>{test.title}</h2>
            <p className="bb-research-test__value">{test.featuredValue}</p>
            <p className="bb-research-test__value-label">{test.featuredLabel}</p>
            <p className="bb-research-test__explanation">{test.explanation}</p>
            <dl className="bb-research-test__stats">
              {test.stats.map(([label, value]) => (
                <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
              ))}
            </dl>
          </article>
        ))}
      </div>

      <div className="bb-research-lower">
        <section className="bb-research-attribution" aria-labelledby="policy-attribution-title">
          <div className="bb-research-section-head">
            <h2 id="policy-attribution-title">Buying versus selling</h2>
          </div>
          <div className="bb-research-table-wrap">
            <table className="bb-research-table">
              <thead><tr><th>Rule</th><th>Money at the end</th><th>Start dates it won</th></tr></thead>
              <tbody>
                {DCA_EVIDENCE.attribution.map(([policy, wealth, wins]) => (
                  <tr key={policy}>
                    <th scope="row">{policy}</th>
                    <td data-label="Money at the end" className={wealth.startsWith("\u2212") ? "bb-research-negative" : ""}>{wealth}</td>
                    <td data-label="Start dates it won">{wins}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="bb-research-caption">
            Same deposits, same trading costs. Selling helped more than varying the buys, but nothing
            here beat simply buying the same amount every month.
          </p>
        </section>

        <aside className="bb-research-guardrails" aria-labelledby="evidence-guardrails-title">
          <h2 id="evidence-guardrails-title">What the test refuses to know</h2>
          <ol>
            {DCA_EVIDENCE.safeguards.map((safeguard) => <li key={safeguard}>{safeguard}</li>)}
          </ol>
          <p className="bb-research-run">Frozen run / {DCA_EVIDENCE.runId}</p>
        </aside>
      </div>

      <p className="bb-research-disclaimer">
        This grades one frozen score and one set of rules. A different selling rule, or a stop-loss,
        or a price target would each need their own test. None of this is investment advice.
      </p>
    </section>
  );
}

function StrategyField({ label, value, min = 0, max, step, onChange, inputRef, invalid, describedBy }) {
  return (
    <label className="bb-dca-field">
      <span>{label}</span>
      <input
        ref={inputRef}
        aria-invalid={invalid || undefined}
        aria-describedby={describedBy}
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

const WATCH_OPTIONS = [
  { key: "both", label: "Either way" },
  { key: "high", label: "Only when it gets high" },
  { key: "low", label: "Only when it gets low" },
];

export function AlertsSignupPanel({ dcaSeries }) {
  const [email, setEmail] = useState("");
  const [watch, setWatch] = useState("both");
  const [buyInput, setBuyInput] = useState(scoreLabel(LOW_MARK));
  const [sellInput, setSellInput] = useState(scoreLabel(HIGH_MARK));
  const [website, setWebsite] = useState("");
  const [status, setStatus] = useState("idle");
  const [message, setMessage] = useState("");

  const [thresholdsOpen, setThresholdsOpen] = useState(false);
  const [thresholdError, setThresholdError] = useState(null);
  const lowRef = useRef(null);
  const highRef = useRef(null);
  useEffect(() => {
    if (thresholdError) (thresholdError === "low" ? lowRef : highRef).current?.focus();
  }, [thresholdError, thresholdsOpen]);

  const low = Number(buyInput);
  const high = Number(sellInput);
  const watchLow = watch !== "high";
  const watchHigh = watch !== "low";
  const validMark = (input) => input.trim() !== "" && Number.isInteger(Number(input)) && Number(input) >= 0 && Number(input) <= 100;
  const invalidSide = watchLow && !validMark(buyInput) ? "low" : watchHigh && !validMark(sellInput) ? "high" : null;
  const overlap = watch === "both" && low >= high;
  const preview = dcaSeries && !invalidSide && !overlap
    ? alertPreview(dcaSeries, { low: low / 100, high: high / 100, watch }) : null;

  async function handleSubmit(event) {
    event.preventDefault();
    if (!EMAIL_PATTERN.test(email.trim())) {
      setStatus("error");
      setMessage("That email address does not look right.");
      return;
    }
    if (invalidSide || overlap) {
      setStatus("error");
      setMessage(invalidSide ? "Use a whole number from 0 to 100." : "The low mark has to sit below the high mark.");
      setThresholdError(invalidSide ?? "low");
      setThresholdsOpen(true);
      return;
    }
    setThresholdError(null);
    setStatus("submitting");
    setMessage("");
    try {
      const response = await fetch("/api/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(),
          watch,
          // An unwatched side's field is hidden and may hold anything, so the
          // default mark is sent in its place.
          buyThreshold: watchLow ? low / 100 : LOW_MARK,
          sellThreshold: watchHigh ? high / 100 : HIGH_MARK,
          website,
        }),
      });
      const data = await response.json().catch(() => null);
      if (response.ok && data?.ok) {
        setStatus("success");
        setMessage(data.message ?? "Check your inbox to confirm.");
      } else {
        setStatus("error");
        setMessage(data?.error ?? "That did not go through. Try again later.");
      }
    } catch {
      setStatus("error");
      setMessage("That did not go through. Try again later.");
    }
  }

  return (
    <section className="bb-panel bb-alerts" id="alerts">
      <div className="bb-panel__head">
        <h2 className="bb-panel__title bb-panel__title--solo">Get an email when it moves</h2>
      </div>

      <form className="bb-alerts-form" onSubmit={handleSubmit} noValidate>
        <fieldset className="bb-choice">
          <legend className="bb-choice__legend">Tell me</legend>
          <div className="bb-choice__options">
            {WATCH_OPTIONS.map((option) => (
              <label key={option.key} className="bb-choice__label">
                <input type="radio" name="watch" value={option.key} checked={watch === option.key}
                  onChange={() => { setWatch(option.key); setThresholdError(null); setMessage(""); }} />
                <span className="bb-choice__option">{option.label}</span>
              </label>
            ))}
          </div>
        </fieldset>

        {preview && (
          <p className="bb-alerts-preview" role="status" data-testid="alert-preview">
            <strong>{preview.count}</strong>{" "}
            {preview.count === 1 ? "email" : "emails"} since {formatDay(preview.since)} at these
            settings{preview.lastEntry ? `, the last on ${formatDay(preview.lastEntry.date)}` : ""}.
          </p>
        )}

        <div className="bb-alerts-row">
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
          <button type="submit" className="bb-button bb-button--primary bb-alerts-submit" disabled={status === "submitting"}>
            {status === "submitting" ? "Sending…" : "Email me"}
          </button>
        </div>

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

        <details className="bb-alerts-advanced" open={thresholdsOpen} onToggle={(event) => setThresholdsOpen(event.currentTarget.open)}>
          <summary>Change the thresholds</summary>
          <div className="bb-dca-controls">
            {watchLow && <StrategyField label="Low at or below" value={buyInput} max={100} step="1" onChange={(v) => { setBuyInput(v); setThresholdError(null); setMessage(""); }} inputRef={lowRef} invalid={thresholdError === "low"} describedBy={thresholdError === "low" ? "threshold-error" : undefined} />}
            {watchHigh && <StrategyField label="High at or above" value={sellInput} max={100} step="1" onChange={(v) => { setSellInput(v); setThresholdError(null); setMessage(""); }} inputRef={highRef} invalid={thresholdError === "high"} describedBy={thresholdError === "high" ? "threshold-error" : undefined} />}
          </div>
        </details>
      </form>

      {message && (
        <p id={thresholdError ? "threshold-error" : undefined} className={`bb-alerts-status bb-alerts-status--${status}`} role="status" data-testid="alert-message">
          {message}
        </p>
      )}

      <p className="bb-dca-note">
        Checked once a day after the data refresh. You confirm by email, and every email has an
        unsubscribe link. Nothing here touches your money.
      </p>
    </section>
  );
}

function ComparisonStrip({ comparisons }) {
  if (comparisons.length < 2) return null;
  return (
    <div className="bb-strip">
      {comparisons.map((entry) => (
        <div className="bb-strip__cell" key={entry.label}>
          <p className="bb-strip__label">{entry.label}</p>
          <p className="bb-strip__value">{scoreLabel(entry.value)}</p>
          <p className="bb-strip__region">{entry.region?.label ?? "—"}</p>
        </div>
      ))}
    </div>
  );
}

function RegionTable({ regionShares, currentKey, since }) {
  const rows = [
    { key: "low", range: "0–25", blurb: "Quiet, well below the peaks of past cycles." },
    { key: "middle", range: "26–74", blurb: "Neither extreme. Where the market spends most of its time." },
    { key: "high", range: "75–100", blurb: "Stretched, and close to how past cycle peaks looked." },
  ];
  return (
    <table className="bb-table bb-regions">
      <caption>Shares count every day since {formatDay(since)}.</caption>
      <thead>
        <tr>
          <th>Reading</th>
          <th>Called</th>
          <th>Share of days</th>
          <th>What it looks like</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const share = regionShares.find((entry) => entry.key === row.key);
          const isCurrent = row.key === currentKey;
          return (
            <tr key={row.key} className={isCurrent ? "bb-regions__row--current" : ""}>
              <td>{row.range}</td>
              <td>
                {share?.label ?? row.key}
                {isCurrent && <span className="bb-regions__here">you are here</span>}
              </td>
              <td data-label="Share of days">{share ? `${Math.round(share.share * 100)}%` : "—"}</td>
              <td>{row.blurb}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function DriverBars({ components, setActiveTab }) {
  const rows = components
    .filter((component) => Number.isFinite(Number(component.latestValue)))
    .sort((a, b) => Number(b.latestValue) - Number(a.latestValue));
  if (!rows.length) return null;

  return (
    <section className="bb-panel bb-drivers">
      <div className="bb-panel__head">
        <h2 className="bb-panel__title bb-panel__title--solo">What is moving it</h2>
        <button type="button" className="bb-link" onClick={() => setActiveTab("method")}>
          How each one works →
        </button>
      </div>
      <ul className="bb-drivers__list">
        {rows.map((component) => {
          const value = Number(component.latestValue);
          return (
            <li className="bb-drivers__item" key={component.key}>
              <span className="bb-drivers__name">{component.label}</span>
              <span className="bb-drivers__track" aria-hidden="true">
                <span className="bb-drivers__fill" style={{ width: `${Math.round(value * 100)}%` }} />
              </span>
              <span className="bb-drivers__value">{scoreLabel(value)}</span>
            </li>
          );
        })}
      </ul>
      <p className="bb-dca-note">
        Each bar is the component&apos;s contribution to the reading, rescaled so 0 is calm and 100
        is heated. That is why the bottoms signal reads inverted here: looking nothing like a past
        bottom pushes risk up.
      </p>
    </section>
  );
}

const CHART_RANGES = [
  { key: "2y", label: "2Y", days: 730 },
  { key: "5y", label: "5Y", days: 1826 },
  { key: "all", label: "All", days: null },
];

function RiskPanel({ historyCore, setActiveTab }) {
  const chartRef = useRef(null);
  const [range, setRange] = useState("2y");
  const dcaSeries = useMemo(() => buildDcaRiskSeries(historyCore), [historyCore]);
  const btcSeries = useMemo(() => chartData(historyCore, "btc_price"), [historyCore]);
  const btcValues = useMemo(
    () => alignOverlayValues(dcaSeries.labels, btcSeries),
    [dcaSeries.labels, btcSeries],
  );
  const summary = useMemo(() => readingSummary(dcaSeries), [dcaSeries]);

  const latestIndex = dcaSeries.labels.length - 1;
  const latestCoverage = latestIndex >= 0 ? Number(dcaSeries.coverageValues?.[latestIndex]) : 0;
  const isDegraded = latestCoverage < 0.75 || !summary;

  const componentRows = dcaSeries.components.map((component) => ({
    ...component,
    latestValue: latestIndex >= 0 ? component.values[latestIndex] : null,
  }));

  const windowSize = CHART_RANGES.find((entry) => entry.key === range)?.days;
  const sliceStart = windowSize ? Math.max(0, dcaSeries.labels.length - windowSize) : 0;
  const labels = dcaSeries.labels.slice(sliceStart);
  const hasBtcData = btcValues.slice(sliceStart).some((value) => value !== null);

  const chartPayload = useMemo(
    () => ({
      labels,
      datasets: [
        {
          label: "Risk",
          data: dcaSeries.values.slice(sliceStart),
          borderColor: COLORS.amber,
          borderWidth: 2.4,
          pointRadius: 0,
          fill: true,
          backgroundColor: "#f0a5001f",
          tension: 0.15,
          yAxisID: "y",
        },
        {
          label: "Low, 25",
          data: labels.map(() => LOW_MARK),
          borderColor: COLORS.green,
          borderDash: [5, 5],
          borderWidth: 1.1,
          pointRadius: 0,
          yAxisID: "y",
        },
        {
          label: "High, 75",
          data: labels.map(() => HIGH_MARK),
          borderColor: COLORS.red,
          borderDash: [5, 5],
          borderWidth: 1.1,
          pointRadius: 0,
          yAxisID: "y",
        },
        ...(hasBtcData
          ? [{
              label: "BTC price",
              data: btcValues.slice(sliceStart),
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
    [labels, dcaSeries.values, sliceStart, hasBtcData, btcValues],
  );

  const options = useMemo(
    () => makeChartOptions({
      numLabels: labels.length,
      hasPrice: hasBtcData,
      priceScaleType: "logarithmic",
      accentColor: COLORS.amber,
    }),
    [labels.length, hasBtcData],
  );

  if (isDegraded) {
    return (
      <section aria-label="Today" className="bb-panel bb-panel--focus">
        <h1 className="bb-panel__title bb-panel__title--solo">No reading today</h1>
        <p className="bb-dca-warning">
          Too many of the underlying sources are missing to publish a number. It comes back once they recover.
        </p>
        {summary && <p className="bb-dca-note">The last published reading was {scoreLabel(summary.latest)} on {formatDay(summary.latestDate)}.</p>}
      </section>
    );
  }

  const tone = summary.region.key === "low" ? "green" : summary.region.key === "high" ? "red" : "amber";
  const percentile = summary.percentileBelow === null ? null : Math.round(summary.percentileBelow * 100);

  return (
    <section aria-label="Today">
      <div className="bb-reading">
        <h1 className="bb-reading__question">How heated does the Bitcoin market look today?</h1>
        <p className={`bb-reading__value bb-card__value--${tone}`}>{scoreLabel(summary.latest)}</p>
        <p className={`bb-reading__region bb-card__value--${tone}`}>{summary.region.label}</p>
        {percentile !== null && (
          <p className="bb-reading__context">
            Higher than {percentile}% of days since {formatDay(summary.firstDate)}.
          </p>
        )}
        <p className="bb-reading__caveat">
          0 is calm, 100 is stretched. It describes today, and says nothing about tomorrow.
        </p>
      </div>

      <ComparisonStrip comparisons={summary.comparisons} />

      <section className="bb-panel bb-panel--focus">
        <div className="bb-panel__head">
          <h2 className="bb-panel__title bb-panel__title--solo">Risk against price</h2>
          <div className="bb-panel__actions">
            <div className="bb-scope-toggle">
              {CHART_RANGES.map((entry) => (
                <button
                  key={entry.key}
                  type="button"
                  className={`bb-scope-btn${range === entry.key ? " bb-scope-btn--active" : ""}`}
                  onClick={() => { chartRef.current?.resetZoom?.(); setRange(entry.key); }}
                >
                  {entry.label}
                </button>
              ))}
            </div>
            <button type="button" className="bb-button" onClick={() => chartRef.current?.resetZoom?.()}>
              Reset zoom
            </button>
          </div>
        </div>
        <div className="bb-chart-wrap bb-chart-wrap--focus" data-testid="risk-chart">
          {labels.length > 0 ? (
            <Line role="img" aria-label={`Risk reading and Bitcoin price, ${CHART_RANGES.find((entry) => entry.key === range)?.label}. Latest reading ${scoreLabel(summary.latest)}.`} ref={chartRef} data={chartPayload} options={options} plugins={[hoverGuidePlugin]} />
          ) : (
            <p className="bb-empty">No data available.</p>
          )}
        </div>
      </section>

      <section className="bb-panel bb-panel--focus">
        <div className="bb-panel__head">
          <h2 className="bb-panel__title bb-panel__title--solo">Reading the number</h2>
        </div>
        <RegionTable
          regionShares={summary.regionShares}
          currentKey={summary.region.key}
          since={summary.firstDate}
        />
        <p className="bb-dca-note">
          Whether these readings are worth acting on is a separate question.{" "}
          <button type="button" className="bb-link" onClick={() => setActiveTab("record")}>
            See what happened when we tested it →
          </button>
        </p>
      </section>

      <DriverBars components={componentRows} setActiveTab={setActiveTab} />

      <AlertsSignupPanel dcaSeries={dcaSeries} />
    </section>
  );
}

const ABOUT_HEADLINE_KEYS = [
  "top_reversal_risk",
  "bottom_reversal_risk",
  "cycle_extension",
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
          <table className="bb-table bb-table--technical">
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

function MethodPanel({ latestSnapshot, historyCore, metricBtc, methodStatus }) {
  return (
    <section className="bb-about" aria-label="Method">
      <div className="bb-about__hero">
        <h1 className="bb-method-title">How the reading is built</h1>
        <p className="bb-about__lede">
          The reading is an average of four sub-scores, each built from public Bitcoin data and
          rescaled against every day of history before it.
        </p>
      </div>

      <div className="bb-card-grid bb-card-grid--focus">
        <MetricCard label="Looks like past peaks" value={latestSnapshot.top_reversal_risk} tone="red" highlight />
        <MetricCard label="Looks like past bottoms" value={latestSnapshot.bottom_reversal_risk} tone="green" highlight />
        <MetricCard label="Price stretch" value={latestSnapshot.cycle_extension_score} tone="amber" highlight />
        <MetricCard
          label="Speculation and hype"
          value={latestSnapshot.cycle_model?.frenzy_score ?? latestSnapshot.cycle_frenzy_score}
          tone="violet"
          highlight
        />
      </div>

      <OverviewPanel historyCore={historyCore} />
      {methodStatus === "ready" ? <MetricsPanel metricBtc={metricBtc} historyCore={historyCore} /> : (
        <section className="bb-panel"><p className="bb-dca-note" role="status">{methodStatus === "error" ? "The raw inputs did not load. Reload to try again." : "Loading the raw inputs…"}</p></section>
      )}

      <div className="bb-about__section">
        <div className="bb-about__section-head">
          <span className="bb-about__rule" />
          <h2 className="bb-about__section-title">The four sub-scores</h2>
        </div>

        {ABOUT_HEADLINE_KEYS.map((key) => (
          <AboutEntry key={key} copy={METRIC_COPY[key]} />
        ))}
      </div>

      <section className="bb-about__section" aria-labelledby="calculation-title">
        <div className="bb-about__section-head">
          <span className="bb-about__rule" />
          <h2 id="calculation-title" className="bb-about__section-title">The calculation, step by step</h2>
        </div>
        <div className="bb-about__methodology">
          <ol className="bb-about__methodology-list">
            {METRIC_COPY.scoring.steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </div>
      </section>

      <section className="bb-about__section">
        <h2 className="bb-about__section-title">Context, not part of the reading</h2>
        <AboutEntry copy={METRIC_COPY.headline_attention} />
      </section>

      <div className="bb-about__section">
        <div className="bb-about__section-head">
          <span className="bb-about__rule" />
          <h2 className="bb-about__section-title">The raw inputs</h2>
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
  const [metricBtc, setMetricBtc] = useState(null);
  const [methodStatus, setMethodStatus] = useState("idle");
  const methodRequest = useRef(null);
  useEffect(() => {
    if (activeTab !== "method" || !payload || methodRequest.current) return;
    setMethodStatus("loading");
    // Cache the request as well as the result, including across tab switches.
    methodRequest.current = loadMethodData(payload.manifest.release_id);
    methodRequest.current.then((data) => {
      setMetricBtc(data);
      setMethodStatus("ready");
    }).catch(() => setMethodStatus("error"));
  }, [activeTab, payload]);

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
    try { window.localStorage.setItem(ACTIVE_TAB_STORAGE_KEY, activeTab); } catch { /* Storage is optional. */ }
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

  const { latestSnapshot, historyCore, diagnostics } = payload;

  return (
    <div className="bb-app">
      <StatusTicker latestSnapshot={latestSnapshot} diagnostics={diagnostics} />

      <main className="bb-main">
        <div className="bb-navigation">
          <button type="button" className="bb-brand" onClick={() => setActiveTab("today")}>
            <span className="bb-brand__mark" aria-hidden="true">◒</span>
            <span>Risk Metric</span>
          </button>
          <nav className="bb-tabs" aria-label="Primary">
            {TABS.map(({ key, label }) => (
              <button
                key={key}
                type="button"
                className={`bb-tab${activeTab === key ? " bb-tab--active" : ""}`}
                onClick={() => setActiveTab(key)}
                aria-current={activeTab === key ? "page" : undefined}
              >
                {label}
              </button>
            ))}
          </nav>
        </div>

        {activeTab === "today" && <RiskPanel historyCore={historyCore} setActiveTab={setActiveTab} />}

        {activeTab === "record" && <TrackRecordPanel />}

        {activeTab === "method" && (
          <MethodPanel
            latestSnapshot={latestSnapshot}
            historyCore={historyCore}
            metricBtc={metricBtc}
            methodStatus={methodStatus}
          />
        )}
      </main>

      <footer className="bb-footer">
        A personal project. Not investment advice.
      </footer>
    </div>
  );
}
