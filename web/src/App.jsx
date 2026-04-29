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

import { chartData, loadDashboardData, valueLabel } from "./data";
import { useBreakdown } from "./useBreakdown";

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
  panelHeader: "#0b0b0b",
  border: "#232323",
  borderDim: "#191919",
  text: "#cbc3ab",
  muted: "#726b5d",
  amber: "#f0a500",
  red: "#ee3333",
  green: "#22cc55",
  blue: "#5ca2ff",
};

const FONT = "'IBM Plex Mono', 'Courier New', monospace";
const PRICE_FORMAT = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

const DAILY_METRIC_ROWS = [
  {
    metric: "btc_trend_extension_50d_350d",
    calc: "SMA_50(BTC close) / SMA_350(BTC close)",
  },
  {
    metric: "btc_running_roi_1y",
    calc: "(BTC_t / BTC_t-365) - 1",
  },
  {
    metric: "btc_log_reg_deviation",
    calc: "BTC close / exp(polyfit(log(time), log(BTC close)))",
  },
  {
    metric: "btc_drawdown_from_ath",
    calc: "(BTC close / cummax(BTC close)) - 1",
  },
  {
    metric: "btc_realized_vol_30d",
    calc: "std(log returns, 30d) * sqrt(365), direction inverted for risk pressure",
  },
  {
    metric: "total_* price-structure metrics",
    calc: "Same formulas as BTC metrics, applied to total market cap",
  },
  {
    metric: "btc_dominance_proxy",
    calc: "(BTC close / max(BTC close)) / (total market cap / max(total market cap))",
  },
  {
    metric: "fear_greed_index",
    calc: "Daily value from alternative.me, normalized in scoring pipeline",
  },
];

const SCORE_ROWS = [
  "Each metric is transformed with rolling robust normalization and a bounded signed heat signal.",
  "Per-category heat and attention are reliability-weighted means of available metrics.",
  "Category weights are then reliability-adjusted and re-normalized each day.",
  "headline_heat = confidence-aware blend of BTC heat and total-market heat (70/30 anchor).",
  "headline_attention = confidence-aware blend of BTC attention and total-market attention (70/30 anchor).",
  "confidence_score = 0.7 * btc_confidence + 0.3 * total_market_confidence.",
];

const CYCLE_ROWS = [
  {
    metric: "cycle_heat_score",
    calc: "Weighted monthly composite of valuation/speculation/attention/macro hot percentiles",
  },
  {
    metric: "cycle_cold_score",
    calc: "1 - category hot scores, aggregated with same category weights",
  },
  {
    metric: "cycle_p_frenzy / cycle_p_accumulation",
    calc: "Logistic mapping of cycle_heat_score / cycle_cold_score with confidence shrinkage",
  },
  {
    metric: "cycle_signal_regime",
    calc: "BUY/HOLD/SELL from threshold + confirmation-months + cooldown rules",
  },
];

const hoverGuidePlugin = {
  id: "hoverGuide",
  afterDatasetsDraw(chart) {
    const activeElements = chart.tooltip?.getActiveElements?.() ?? [];
    if (!activeElements.length) {
      return;
    }

    const x = activeElements[0]?.element?.x;
    const { top, bottom } = chart.chartArea || {};
    if (!Number.isFinite(x) || !Number.isFinite(top) || !Number.isFinite(bottom)) {
      return;
    }

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

function alignSeries(primary, secondary) {
  const secondaryMap = new Map();
  secondary.labels.forEach((label, idx) => {
    secondaryMap.set(label, secondary.values[idx] ?? null);
  });

  const labels = [];
  const primaryValues = [];
  const secondaryValues = [];

  primary.labels.forEach((label, idx) => {
    if (!secondaryMap.has(label)) {
      return;
    }
    labels.push(label);
    primaryValues.push(primary.values[idx] ?? null);
    secondaryValues.push(secondaryMap.get(label) ?? null);
  });

  return {
    labels,
    primaryValues,
    secondaryValues,
  };
}

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

function cycleRegimeLabel(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) {
    return "n/a";
  }
  if (num >= 0.7) {
    return "Historically Hot";
  }
  if (num <= 0.3) {
    return "Historically Cold";
  }
  return "Neutral Band";
}

function snapshotCards(latestSnapshot) {
  return [
    { label: "Headline Heat", value: latestSnapshot.headline_heat, tone: "red" },
    { label: "Headline Attention", value: latestSnapshot.headline_attention, tone: "amber" },
    { label: "Cycle Regime Index", value: latestSnapshot.cycle_model?.heat_score, tone: "red" },
    { label: "Cycle Confidence", value: latestSnapshot.cycle_model?.confidence, tone: "blue" },
    { label: "BTC Risk Heat", value: latestSnapshot.btc_risk?.heat, tone: "red" },
    { label: "BTC Risk Attention", value: latestSnapshot.btc_risk?.attention, tone: "amber" },
    { label: "Total Market Heat", value: latestSnapshot.total_market_risk?.heat, tone: "red" },
    { label: "Total Market Attention", value: latestSnapshot.total_market_risk?.attention, tone: "amber" },
    { label: "Confidence Score", value: latestSnapshot.confidence_score, tone: "blue" },
  ];
}

function StatusTicker({ manifest }) {
  return (
    <header className="bb-topbar">
      <span className="bb-brand">RISK METRIC</span>
      <div className="bb-topbar__spacer" />
      <span className="bb-meta">LAST PRINT {manifest.generated_at}</span>
    </header>
  );
}

function MetricCard({ label, value, tone = "amber", highlight = false }) {
  return (
    <article className={`bb-card${highlight ? " bb-card--highlight" : ""}`}>
      <p className="bb-card__label">{label}</p>
      <p className={`bb-card__value bb-card__value--${tone}`}>{valueLabel(value)}</p>
    </article>
  );
}

function FocusPanel({
  heatSeries,
  attentionSeries,
  btcSeries,
  cycleSeries,
  cycleConfidenceSeries,
  latestCycleValue,
  latestCycleConfidence,
}) {
  const chartRef = useRef(null);
  const cycleChartRef = useRef(null);
  const [btcScaleType, setBtcScaleType] = useState("logarithmic");

  const merged = useMemo(() => alignSeries(heatSeries, attentionSeries), [heatSeries, attentionSeries]);
  const btcOverlayValues = useMemo(
    () => alignOverlayValues(merged.labels, btcSeries),
    [merged.labels, btcSeries],
  );
  const hasBtcOverlay = btcOverlayValues.some((value) => value !== null);
  const hasData = merged.labels.length > 0;
  const cycleConfidenceValues = useMemo(
    () => alignOverlayValues(cycleSeries.labels, cycleConfidenceSeries),
    [cycleSeries.labels, cycleConfidenceSeries],
  );
  const cycleBtcOverlayValues = useMemo(
    () => alignOverlayValues(cycleSeries.labels, btcSeries),
    [cycleSeries.labels, btcSeries],
  );
  const hasCycleData = cycleSeries.labels.length > 0;
  const hasCycleBtcOverlay = cycleBtcOverlayValues.some((value) => value !== null);

  const chartDataPayload = useMemo(() => {
    if (!hasData) {
      return { labels: [], datasets: [] };
    }
    return {
      labels: merged.labels,
      datasets: [
        {
          label: "Headline Heat",
          data: merged.primaryValues,
          borderColor: COLORS.red,
          borderWidth: 1.9,
          pointRadius: 0,
          fill: true,
          backgroundColor: "#ee33331f",
          tension: 0.16,
        },
        {
          label: "Headline Attention",
          data: merged.secondaryValues,
          borderColor: COLORS.amber,
          borderWidth: 1.9,
          pointRadius: 0,
          fill: true,
          backgroundColor: "#f0a50019",
          tension: 0.16,
        },
        ...(hasBtcOverlay
          ? [
              {
                label: "BTC Price",
                data: btcOverlayValues,
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
    };
  }, [hasData, merged, hasBtcOverlay, btcOverlayValues]);

  const chartOptions = useMemo(
    () => ({
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false,
      },
      scales: {
        x: {
          ticks: {
            maxTicksLimit: 8,
            color: COLORS.muted,
            font: { family: FONT, size: 10 },
          },
          grid: { color: COLORS.borderDim },
          border: { color: COLORS.border },
        },
        y: {
          min: 0,
          max: 1,
          ticks: {
            color: COLORS.muted,
            font: { family: FONT, size: 10 },
          },
          grid: { color: COLORS.borderDim },
          border: { color: COLORS.border },
        },
        yPrice: {
          display: hasBtcOverlay,
          position: "right",
          type: btcScaleType,
          ticks: {
            callback: (tickValue) => formatPrice(tickValue),
            color: "#8f8b80",
            font: { family: FONT, size: 10 },
          },
          grid: { drawOnChartArea: false },
          border: { color: COLORS.border },
        },
      },
      plugins: {
        legend: {
          display: true,
          labels: {
            color: COLORS.text,
            font: { family: FONT, size: 11 },
            boxWidth: 10,
          },
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
            label: (item) => (
              item.dataset.yAxisID === "yPrice"
                ? `${item.dataset.label}: ${formatPrice(item.parsed.y)}`
                : `${item.dataset.label}: ${valueLabel(item.parsed.y, 4)}`
            ),
          },
        },
        zoom: {
          limits: {
            x: {
              min: 0,
              max: Math.max(0, merged.labels.length - 1),
            },
          },
          pan: {
            enabled: true,
            mode: "x",
          },
          zoom: {
            mode: "x",
            wheel: { enabled: true },
            pinch: { enabled: true },
            drag: {
              enabled: true,
              backgroundColor: "#f0a5001f",
              borderColor: COLORS.amber,
              borderWidth: 1,
            },
          },
        },
      },
    }),
    [merged.labels.length, hasBtcOverlay, btcScaleType],
  );

  const cycleChartDataPayload = useMemo(() => {
    if (!hasCycleData) {
      return { labels: [], datasets: [] };
    }
    return {
      labels: cycleSeries.labels,
      datasets: [
        {
          label: "Cycle Regime Index (0=cold, 1=hot)",
          data: cycleSeries.values,
          borderColor: COLORS.red,
          borderWidth: 1.9,
          pointRadius: 0,
          fill: true,
          backgroundColor: "#ee333324",
          tension: 0.14,
        },
        {
          label: "Cycle Confidence",
          data: cycleConfidenceValues,
          borderColor: COLORS.blue,
          borderWidth: 1.5,
          borderDash: [4, 4],
          pointRadius: 0,
          fill: false,
          tension: 0.14,
        },
        ...(hasCycleBtcOverlay
          ? [
              {
                label: "BTC Price",
                data: cycleBtcOverlayValues,
                borderColor: "#8b8473",
                borderWidth: 1.2,
                pointRadius: 0,
                fill: false,
                tension: 0.1,
                yAxisID: "yPrice",
              },
            ]
          : []),
      ],
    };
  }, [hasCycleData, cycleSeries, cycleConfidenceValues, hasCycleBtcOverlay, cycleBtcOverlayValues]);

  const cycleChartOptions = useMemo(
    () => ({
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false,
      },
      scales: {
        x: {
          ticks: {
            maxTicksLimit: 8,
            color: COLORS.muted,
            font: { family: FONT, size: 10 },
          },
          grid: { color: COLORS.borderDim },
          border: { color: COLORS.border },
        },
        y: {
          min: 0,
          max: 1,
          ticks: {
            color: COLORS.muted,
            font: { family: FONT, size: 10 },
          },
          grid: { color: COLORS.borderDim },
          border: { color: COLORS.border },
        },
        yPrice: {
          display: hasCycleBtcOverlay,
          position: "right",
          type: btcScaleType,
          ticks: {
            callback: (tickValue) => formatPrice(tickValue),
            color: "#8f8b80",
            font: { family: FONT, size: 10 },
          },
          grid: { drawOnChartArea: false },
          border: { color: COLORS.border },
        },
      },
      plugins: {
        legend: {
          display: true,
          labels: {
            color: COLORS.text,
            font: { family: FONT, size: 11 },
            boxWidth: 10,
          },
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
            label: (item) => (
              item.dataset.yAxisID === "yPrice"
                ? `${item.dataset.label}: ${formatPrice(item.parsed.y)}`
                : `${item.dataset.label}: ${valueLabel(item.parsed.y, 4)}`
            ),
          },
        },
        zoom: {
          limits: {
            x: {
              min: 0,
              max: Math.max(0, cycleSeries.labels.length - 1),
            },
          },
          pan: {
            enabled: true,
            mode: "x",
          },
          zoom: {
            mode: "x",
            wheel: { enabled: true },
            pinch: { enabled: true },
            drag: {
              enabled: true,
              backgroundColor: "#5ca2ff1f",
              borderColor: COLORS.blue,
              borderWidth: 1,
            },
          },
        },
      },
    }),
    [cycleSeries.labels.length, hasCycleBtcOverlay, btcScaleType],
  );

  return (
    <section className="bb-panel bb-panel--focus">
      <div className="bb-panel__head">
        <div>
          <p className="bb-panel__eyebrow">Focus</p>
          <h2 className="bb-panel__title">Headline Heat + Headline Attention</h2>
        </div>
        <div className="bb-panel__actions">
          <label className="bb-checkbox">
            BTC SCALE
            <select className="bb-select bb-select--compact" value={btcScaleType} onChange={(event) => setBtcScaleType(event.target.value)}>
              <option value="logarithmic">LOG</option>
              <option value="linear">LINEAR</option>
            </select>
          </label>
          <button type="button" className="bb-button" onClick={() => chartRef.current?.resetZoom?.()}>
            Reset Zoom
          </button>
          <button type="button" className="bb-button" onClick={() => cycleChartRef.current?.resetZoom?.()}>
            Reset Cycle Zoom
          </button>
        </div>
      </div>
      <div className="bb-cycle-strip">
        <p className="bb-cycle-strip__title">Cycle Regime Index (CRI)</p>
        <p className="bb-cycle-strip__value">{valueLabel(latestCycleValue, 3)}</p>
        <p className="bb-cycle-strip__state">{cycleRegimeLabel(latestCycleValue)}</p>
        <p className="bb-cycle-strip__meta">Confidence {valueLabel(latestCycleConfidence, 3)}</p>
      </div>
      <div className="bb-chart-wrap bb-chart-wrap--focus" data-testid="focus-chart">
        {hasData ? (
          <Line ref={chartRef} data={chartDataPayload} options={chartOptions} plugins={[hoverGuidePlugin]} />
        ) : (
          <p className="bb-empty">No focus-series data available.</p>
        )}
      </div>
      <div className="bb-chart-wrap bb-chart-wrap--cycle" data-testid="cycle-chart">
        {hasCycleData ? (
          <Line ref={cycleChartRef} data={cycleChartDataPayload} options={cycleChartOptions} plugins={[hoverGuidePlugin]} />
        ) : (
          <p className="bb-empty">No cycle-series data available.</p>
        )}
      </div>
      <p className="bb-hint">Scroll to zoom, drag to zoom a range, drag horizontally to pan, and hover to inspect values at each date.</p>
      <p className="bb-hint">
        CRI is a normalized 0-1 multi-year regime estimate: lower values imply historically cheaper conditions, higher values imply historically hotter conditions.
      </p>
    </section>
  );
}

function chartOptions(showOverlay, hasOverlayData, overlayScaleType = "linear") {
  return {
    animation: false,
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    scales: {
      x: {
        ticks: {
          maxTicksLimit: 7,
          color: COLORS.muted,
          font: { family: FONT, size: 10 },
        },
        grid: { color: COLORS.borderDim },
        border: { color: COLORS.border },
      },
      y: {
        ticks: {
          color: COLORS.muted,
          font: { family: FONT, size: 10 },
        },
        grid: { color: COLORS.borderDim },
        border: { color: COLORS.border },
      },
      yOverlay: {
        display: showOverlay && hasOverlayData,
        position: "right",
        type: overlayScaleType,
        ticks: {
          callback: (tickValue) => formatPrice(tickValue),
          color: "#8f8b80",
          font: { family: FONT, size: 10 },
        },
        grid: { drawOnChartArea: false },
        border: { color: COLORS.border },
      },
    },
    plugins: {
      legend: {
        display: showOverlay && hasOverlayData,
        labels: {
          color: COLORS.text,
          font: { family: FONT, size: 10 },
        },
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
          label: (item) => (
            item.dataset.yAxisID === "yOverlay"
              ? `${item.dataset.label}: ${formatPrice(item.parsed.y)}`
              : `${item.dataset.label}: ${valueLabel(item.parsed.y, 4)}`
          ),
        },
      },
    },
  };
}

function BreakdownPanel({
  title,
  payload,
  color,
  overlayPayload,
  overlayColumn,
  overlayLabel,
  defaultOverlayScale = "linear",
  overlayScaleToggle = false,
}) {
  const {
    columns,
    selectedColumn,
    setSelectedColumn,
    showOverlay,
    setShowOverlay,
    series,
    latestContributions,
    hasOverlayData,
  } = useBreakdown(payload, overlayPayload, overlayColumn);
  const [overlayScaleType, setOverlayScaleType] = useState(defaultOverlayScale);

  useEffect(() => {
    setOverlayScaleType(defaultOverlayScale);
  }, [defaultOverlayScale]);

  const datasets = [
    {
      label: selectedColumn,
      data: series.values,
      borderColor: color,
      borderWidth: 1.7,
      pointRadius: 0,
      fill: true,
      backgroundColor: `${color}1d`,
      tension: 0.18,
      yAxisID: "y",
    },
    ...(showOverlay && hasOverlayData
      ? [
          {
            label: overlayLabel,
            data: series.overlayValues,
            borderColor: "#7d7666",
            borderWidth: 1.1,
            pointRadius: 0,
            fill: false,
            tension: 0.14,
            yAxisID: "yOverlay",
          },
        ]
      : []),
  ];

  return (
    <section className="bb-panel">
      <div className="bb-panel__head bb-panel__head--tight">
        <h3 className="bb-panel__title bb-panel__title--small">{title}</h3>
        <div className="bb-controls">
          <label className="bb-checkbox">
            <input
              type="checkbox"
              checked={showOverlay}
              onChange={(event) => setShowOverlay(event.target.checked)}
              disabled={!hasOverlayData}
            />
            + {overlayLabel}
          </label>
          {overlayScaleToggle && hasOverlayData && (
            <label className="bb-checkbox">
              BTC SCALE
              <select
                className="bb-select bb-select--compact"
                value={overlayScaleType}
                onChange={(event) => setOverlayScaleType(event.target.value)}
                disabled={!showOverlay}
              >
                <option value="logarithmic">LOG</option>
                <option value="linear">LINEAR</option>
              </select>
            </label>
          )}
          <select className="bb-select" value={selectedColumn} onChange={(event) => setSelectedColumn(event.target.value)}>
            {columns.map((name) => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
        </div>
      </div>
      <div className="bb-chart-wrap bb-chart-wrap--debug">
        <Line
          data={{ labels: series.labels, datasets }}
          options={chartOptions(showOverlay, hasOverlayData, overlayScaleType)}
          plugins={[hoverGuidePlugin]}
        />
      </div>
      <p className="bb-table-title">Top Heat Contributions</p>
      <table className="bb-table">
        <thead>
          <tr>
            <th>Signal</th>
            <th style={{ textAlign: "right" }}>Value</th>
          </tr>
        </thead>
        <tbody>
          {latestContributions.length === 0
            ? (
              <tr><td colSpan={2}>No data</td></tr>
            )
            : latestContributions.map((item) => (
              <tr key={item.name}>
                <td>{item.name}</td>
                <td>{valueLabel(item.value, 4)}</td>
              </tr>
            ))}
        </tbody>
      </table>
    </section>
  );
}

function DiagnosticsPanel({ diagnostics }) {
  const sourceModes = useMemo(() => {
    const rows = Array.isArray(diagnostics?.source_modes) ? diagnostics.source_modes : [];
    const map = new Map();
    rows.forEach((row) => map.set(row.source, row.mode));
    return map;
  }, [diagnostics]);

  const sourceHealth = Array.isArray(diagnostics?.source_health) ? diagnostics.source_health : [];
  const sanity = Array.isArray(diagnostics?.sanity_report) ? diagnostics.sanity_report : [];
  const warnings = Array.isArray(diagnostics?.validation?.warnings) ? diagnostics.validation.warnings : [];

  return (
    <section className="bb-panel">
      <div className="bb-panel__head bb-panel__head--tight">
        <h3 className="bb-panel__title bb-panel__title--small">System Diagnostics</h3>
      </div>
      <div className="bb-diag-grid">
        <div>
          <p className="bb-table-title">Source Availability</p>
          <table className="bb-table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Avail</th>
                <th>Mode</th>
                <th style={{ textAlign: "right" }}>Stale (d)</th>
              </tr>
            </thead>
            <tbody>
              {sourceHealth.map((row) => (
                <tr key={row.source}>
                  <td>{row.source}</td>
                  <td style={{ color: row.available ? COLORS.green : COLORS.red }}>{row.available ? "YES" : "NO"}</td>
                  <td>{sourceModes.get(row.source) || "unknown"}</td>
                  <td>{row.staleness_days ?? "n/a"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div>
          <p className="bb-table-title">Sanity Report</p>
          <table className="bb-table">
            <thead>
              <tr>
                <th>Check</th>
                <th>Pass</th>
                <th>Value</th>
                <th style={{ textAlign: "right" }}>Threshold</th>
              </tr>
            </thead>
            <tbody>
              {sanity.map((row) => (
                <tr key={row.check}>
                  <td>{row.check}</td>
                  <td style={{ color: row.passed ? COLORS.green : COLORS.red }}>{row.passed ? "YES" : "NO"}</td>
                  <td>{row.value ?? "n/a"}</td>
                  <td>{row.threshold ?? "n/a"}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {warnings.length > 0 && (
            <div className="bb-warnings">
              <p className="bb-table-title">Validation Warnings</p>
              <ul>
                {warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function MethodologyPanel() {
  return (
    <section className="bb-panel bb-panel--methodology" aria-label="Methodology panel">
      <div className="bb-panel__head bb-panel__head--tight">
        <h3 className="bb-panel__title bb-panel__title--small">Technical Methodology</h3>
      </div>
      <div className="bb-method">
        <p className="bb-method__title">Daily Metrics (Current Core)</p>
        <table className="bb-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th>Calculation</th>
            </tr>
          </thead>
          <tbody>
            {DAILY_METRIC_ROWS.map((row) => (
              <tr key={row.metric}>
                <td>{row.metric}</td>
                <td>{row.calc}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <p className="bb-method__title">Scoring</p>
        <ul className="bb-method__list">
          {SCORE_ROWS.map((row) => (
            <li key={row}>{row}</li>
          ))}
        </ul>

        <p className="bb-method__title">Cycle Model Outputs</p>
        <table className="bb-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th>Calculation</th>
            </tr>
          </thead>
          <tbody>
            {CYCLE_ROWS.map((row) => (
              <tr key={row.metric}>
                <td>{row.metric}</td>
                <td>{row.calc}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function App() {
  const [status, setStatus] = useState("loading");
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("focus");
  const [showMethodology, setShowMethodology] = useState(false);

  useEffect(() => {
    let active = true;

    loadDashboardData()
      .then((data) => {
        if (!active) {
          return;
        }
        setPayload(data);
        setStatus("ready");
      })
      .catch((err) => {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Unknown data load error");
        setStatus("error");
      });

    return () => {
      active = false;
    };
  }, []);

  if (status === "loading") {
    return <div className="bb-app"><p className="bb-status">LOADING DASHBOARD<span className="bb-blink">_</span></p></div>;
  }

  if (status === "error") {
    return <div className="bb-app"><p className="bb-status bb-status--error">ERROR: {error}</p></div>;
  }

  const {
    latestSnapshot,
    historyCore,
    categoryBtc,
    categoryTotal,
    metricBtc,
    metricTotal,
    diagnostics,
    manifest,
  } = payload;

  const heatSeries = chartData(historyCore, "headline_heat");
  const attentionSeries = chartData(historyCore, "headline_attention");
  const btcSeries = chartData(historyCore, "btc_price");
  const cycleSeries = chartData(historyCore, "cycle_heat_score");
  const cycleConfidenceSeries = chartData(historyCore, "cycle_confidence");

  const cards = snapshotCards(latestSnapshot);

  return (
    <div className="bb-app">
      <StatusTicker manifest={manifest} />

      <main className="bb-main">
        <div className="bb-tabs" role="tablist" aria-label="Dashboard Views">
          <button
            type="button"
            className={`bb-tab${activeTab === "focus" ? " bb-tab--active" : ""}`}
            onClick={() => setActiveTab("focus")}
            role="tab"
            aria-selected={activeTab === "focus"}
          >
            Focus
          </button>
          <button
            type="button"
            className={`bb-tab${activeTab === "debug" ? " bb-tab--active" : ""}`}
            onClick={() => setActiveTab("debug")}
            role="tab"
            aria-selected={activeTab === "debug"}
          >
            Debug
          </button>
          <button
            type="button"
            className={`bb-tab${showMethodology ? " bb-tab--active" : ""}`}
            onClick={() => setShowMethodology((prev) => !prev)}
            aria-expanded={showMethodology}
            aria-controls="bb-methodology"
          >
            Info
          </button>
        </div>

        {showMethodology && (
          <div id="bb-methodology">
            <MethodologyPanel />
          </div>
        )}

        {activeTab === "focus" ? (
          <section aria-label="Focus view">
            <div className="bb-card-grid bb-card-grid--focus">
              <MetricCard label="Headline Heat" value={latestSnapshot.headline_heat} tone="red" highlight />
              <MetricCard label="Headline Attention" value={latestSnapshot.headline_attention} tone="amber" highlight />
              <MetricCard label="Cycle Regime Index" value={latestSnapshot.cycle_model?.heat_score} tone="red" highlight />
              <MetricCard label="Cycle Confidence" value={latestSnapshot.cycle_model?.confidence} tone="blue" />
              <MetricCard label="Confidence Score" value={latestSnapshot.confidence_score} tone="blue" />
            </div>
            <div className="bb-note-panel">
              <p className="bb-note-panel__title">New Multi-Year Cycle Baseline</p>
              <p className="bb-note-panel__text">
                Added a monthly cycle model from free data (valuation, speculation, attention, macro), projected daily as CRI in normalized 0-1 form for broad historical expensiveness vs cheapness context.
              </p>
            </div>
            <FocusPanel
              heatSeries={heatSeries}
              attentionSeries={attentionSeries}
              btcSeries={btcSeries}
              cycleSeries={cycleSeries}
              cycleConfidenceSeries={cycleConfidenceSeries}
              latestCycleValue={latestSnapshot.cycle_model?.heat_score}
              latestCycleConfidence={latestSnapshot.cycle_model?.confidence}
            />
          </section>
        ) : (
          <section aria-label="Debug view">
            <p className="bb-section-title">Current Snapshot</p>
            <div className="bb-card-grid">
              {cards.map((card) => (
                <MetricCard
                  key={card.label}
                  label={card.label}
                  value={card.value}
                  tone={card.tone}
                  highlight={card.label === "Headline Heat" || card.label === "Headline Attention"}
                />
              ))}
            </div>

            <p className="bb-section-title">Category Breakdowns</p>
            <div className="bb-panel-grid bb-panel-grid--two">
              <BreakdownPanel
                title="Category — BTC"
                payload={categoryBtc}
                color={COLORS.red}
                overlayPayload={historyCore}
                overlayColumn="btc_price"
                overlayLabel="BTC Price"
                defaultOverlayScale="logarithmic"
                overlayScaleToggle
              />
              <BreakdownPanel
                title="Category — Total Market"
                payload={categoryTotal}
                color={COLORS.amber}
                overlayPayload={historyCore}
                overlayColumn="total_market_cap"
                overlayLabel="Market Cap"
              />
            </div>

            <p className="bb-section-title">Metric Breakdowns</p>
            <div className="bb-panel-grid bb-panel-grid--two">
              <BreakdownPanel
                title="Metric — BTC"
                payload={metricBtc}
                color={COLORS.green}
                overlayPayload={historyCore}
                overlayColumn="btc_price"
                overlayLabel="BTC Price"
                defaultOverlayScale="logarithmic"
                overlayScaleToggle
              />
              <BreakdownPanel
                title="Metric — Total Market"
                payload={metricTotal}
                color={COLORS.blue}
                overlayPayload={historyCore}
                overlayColumn="total_market_cap"
                overlayLabel="Market Cap"
              />
            </div>

            <p className="bb-section-title">Diagnostics</p>
            <DiagnosticsPanel diagnostics={diagnostics} />
          </section>
        )}
      </main>
    </div>
  );
}
