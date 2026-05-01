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

function makeChartOptions({
  numLabels,
  hasPrice,
  priceScaleType,
  accentColor,
  yAutoScale = false,
  yDomain = [0, 1],
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
        display: true,
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

function StatusTicker({ manifest }) {
  return (
    <header className="bb-topbar">
      <span className="bb-brand">RISK METRIC</span>
      <div className="bb-topbar__spacer" />
      <span className="bb-meta">LAST PRINT {manifest.generated_at}</span>
    </header>
  );
}

function OverviewPanel({ historyCore, setActiveTab }) {
  const chartRef = useRef(null);
  const [visible, setVisible] = useState({ heat: true, attention: true, cycle: true, price: true });
  const [priceScaleType, setPriceScaleType] = useState("logarithmic");

  const heatSeries = useMemo(() => chartData(historyCore, "headline_heat"), [historyCore]);
  const attnValues = useMemo(
    () => alignOverlayValues(heatSeries.labels, chartData(historyCore, "headline_attention")),
    [heatSeries.labels, historyCore],
  );
  const cycleValues = useMemo(
    () => alignOverlayValues(heatSeries.labels, chartData(historyCore, "cycle_heat_score")),
    [heatSeries.labels, historyCore],
  );
  const btcValues = useMemo(
    () => alignOverlayValues(heatSeries.labels, chartData(historyCore, "btc_price")),
    [heatSeries.labels, historyCore],
  );

  const hasBtcData = btcValues.some((v) => v !== null);
  const showPrice = visible.price && hasBtcData;

  const datasets = useMemo(() => {
    const ds = [];
    if (visible.heat) {
      ds.push({
        label: "Heat",
        data: heatSeries.values,
        borderColor: COLORS.red,
        borderWidth: 1.9,
        pointRadius: 0,
        fill: true,
        backgroundColor: "#ee33331f",
        tension: 0.16,
      });
    }
    if (visible.attention) {
      ds.push({
        label: "Attention",
        data: attnValues,
        borderColor: COLORS.amber,
        borderWidth: 1.9,
        pointRadius: 0,
        fill: true,
        backgroundColor: "#f0a50019",
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
  }, [visible, heatSeries.values, attnValues, cycleValues, btcValues, showPrice]);

  const chartPayload = useMemo(
    () => ({ labels: heatSeries.labels, datasets }),
    [heatSeries.labels, datasets],
  );

  const options = useMemo(
    () =>
      makeChartOptions({
        numLabels: heatSeries.labels.length,
        hasPrice: showPrice,
        priceScaleType,
        accentColor: COLORS.amber,
      }),
    [heatSeries.labels.length, showPrice, priceScaleType],
  );

  function toggle(key) {
    setVisible((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  return (
    <section className="bb-panel bb-panel--focus">
      <div className="bb-panel__head">
        <h2 className="bb-panel__title bb-panel__title--solo">Market Indices</h2>
        <div className="bb-panel__actions">
          <label className="bb-checkbox">
            <input type="checkbox" checked={visible.heat} onChange={() => toggle("heat")} />
            Heat
          </label>
          <label className="bb-checkbox">
            <input type="checkbox" checked={visible.attention} onChange={() => toggle("attention")} />
            Attention
          </label>
          <label className="bb-checkbox">
            <input type="checkbox" checked={visible.cycle} onChange={() => toggle("cycle")} />
            Cycle Regime
          </label>
          <label className="bb-checkbox">
            <input
              type="checkbox"
              checked={visible.price}
              onChange={() => toggle("price")}
              disabled={!hasBtcData}
            />
            BTC Price
          </label>
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
      <div className="bb-chart-wrap bb-chart-wrap--focus" data-testid="overview-chart">
        {heatSeries.labels.length > 0 ? (
          <Line ref={chartRef} data={chartPayload} options={options} plugins={[hoverGuidePlugin]} />
        ) : (
          <p className="bb-empty">No data available.</p>
        )}
      </div>
      <div className="bb-overview-desc">
        <p>
          Heat, Attention, and the Cycle Regime Index are three independent estimates of where the
          market sits relative to its historical range. They are computed from different signal
          categories and may agree or diverge.
        </p>
        <p>
          All three are normalized to 0-1. A higher reading indicates conditions historically
          associated with more stretched market positioning. It does not predict what happens
          next.{" "}
          <button type="button" className="bb-link" onClick={() => setActiveTab("about")}>
            Details in About →
          </button>
        </p>
        <p className="bb-overview-note">Attention and Cycle Regime data begins December 2014.</p>
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
  const hasTotal = metric?.totalColumn !== null;
  const copy = METRIC_COPY[metric?.copyKey];

  useEffect(() => {
    setScope("btc");
    chartRef.current?.resetZoom?.();
  }, [selectedKey]);

  const activeColumn =
    scope === "total" && hasTotal ? metric.totalColumn : metric.btcColumn;
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
          label: copy.shortName,
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
    [series, priceValues, hasPrice, copy.shortName, priceLabel],
  );

  const options = useMemo(
    () =>
      makeChartOptions({
        numLabels: series.labels.length,
        hasPrice,
        priceScaleType,
        accentColor: COLORS.amber,
        yDomain: [-1, 1],
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
        <p className="bb-metric-desc__text">{copy.description}</p>
        <p className="bb-metric-desc__link">
          <button type="button" className="bb-link" onClick={() => setActiveTab("about")}>
            Details in About →
          </button>
        </p>
      </div>
    </section>
  );
}

const ABOUT_HEADLINE_KEYS = ["headline_heat", "headline_attention", "cycle_regime"];

function AboutPanel() {
  return (
    <section className="bb-about">
      <div className="bb-about__intro">
        <p>
          A personal project exploring quantitative approaches to understanding Bitcoin market cycles.
          The three headline indices (Heat, Attention, and the Cycle Regime Index) are composite
          signals that synthesize structural, on-chain, and sentiment data to describe where the
          market appears to sit relative to its historical range. The input metrics below feed into
          those composites.
        </p>
      </div>

      <div className="bb-about__section-title">Headline Indices</div>

      {ABOUT_HEADLINE_KEYS.map((key) => {
        const copy = METRIC_COPY[key];
        return (
          <div key={key} className="bb-about__entry">
            <div className="bb-about__entry-name">{copy.shortName}</div>
            <p className="bb-about__desc">{copy.description}</p>
            <p className="bb-about__not">{copy.notMeaning}</p>
            <details className="bb-about__technical">
              <summary>Technical</summary>
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
        );
      })}

      <details className="bb-about__technical bb-about__scoring">
        <summary>Scoring Methodology</summary>
        <ul>
          {METRIC_COPY.scoring.steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ul>
      </details>

      <div className="bb-about__section-title">Input Metrics</div>

      {CURATED_METRICS.filter((m) => m.key !== "mvrv").map((m) => {
        const copy = METRIC_COPY[m.copyKey];
        return (
          <div key={m.key} className="bb-about__entry">
            <div className="bb-about__entry-name">{copy.shortName}</div>
            <p className="bb-about__desc">{copy.description}</p>
            <details className="bb-about__technical">
              <summary>Technical</summary>
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
        );
      })}
    </section>
  );
}

export default function App() {
  const [status, setStatus] = useState("loading");
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("overview");

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

  const { latestSnapshot, historyCore, metricBtc, manifest } = payload;

  return (
    <div className="bb-app">
      <StatusTicker manifest={manifest} />

      <main className="bb-main">
        <div className="bb-tabs" role="tablist" aria-label="Dashboard Views">
          {[
            { key: "overview", label: "Overview" },
            { key: "metrics", label: "Metrics" },
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
              <MetricCard label="Heat" value={latestSnapshot.headline_heat} tone="red" highlight />
              <MetricCard label="Attention" value={latestSnapshot.headline_attention} tone="amber" highlight />
              <MetricCard label="Cycle Regime Index" value={latestSnapshot.cycle_model?.heat_score} tone="violet" highlight />
            </div>
            <OverviewPanel historyCore={historyCore} setActiveTab={setActiveTab} />
          </section>
        )}

        {activeTab === "metrics" && (
          <section aria-label="Metrics">
            <MetricsPanel metricBtc={metricBtc} historyCore={historyCore} setActiveTab={setActiveTab} />
          </section>
        )}

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
