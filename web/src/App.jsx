import { useEffect, useMemo, useState } from "react";
import {
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LogarithmicScale,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from "chart.js";
import { Line } from "react-chartjs-2";

import { chartData, listColumns, loadDashboardData, pickLatestContributions, valueLabel } from "./data";

ChartJS.register(CategoryScale, LineElement, LinearScale, LogarithmicScale, PointElement, Tooltip, Legend, Filler);

function StatCard({ label, value, tone = "neutral" }) {
  return (
    <article className={`stat-card stat-card--${tone}`}>
      <p className="stat-card__label">{label}</p>
      <p className="stat-card__value">{value}</p>
    </article>
  );
}

function TrendChart({ title, labels, values, yBounds, color, showOverlay, overlayValues, overlayLabel, overlayLogScale }) {
  const hasOverlayData = Array.isArray(overlayValues) && overlayValues.some((value) => value !== null);
  const dataset = useMemo(
    () => ({
      labels,
      datasets: [
        {
          label: title,
          data: values,
          borderColor: color,
          borderWidth: 2,
          pointRadius: 0,
          fill: true,
          backgroundColor: `${color}33`,
          tension: 0.2,
          yAxisID: "y",
        },
        ...(showOverlay && hasOverlayData
          ? [
              {
                label: overlayLabel,
                data: overlayValues,
                borderColor: "#2c3e50",
                borderWidth: 1.4,
                pointRadius: 0,
                fill: false,
                tension: 0.15,
                yAxisID: "yPrice",
              },
            ]
          : []),
      ],
    }),
    [title, labels, values, color, showOverlay, hasOverlayData, overlayLabel, overlayValues],
  );

  return (
    <section className="panel">
      <h3>{title}</h3>
      <div className="chart-wrap">
        <Line
          data={dataset}
          options={{
            animation: false,
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              x: {
                ticks: { maxTicksLimit: 8, color: "#5a5c66" },
                grid: { color: "#e7e9ee" },
              },
              y: {
                suggestedMin: yBounds?.[0],
                suggestedMax: yBounds?.[1],
                ticks: { color: "#5a5c66" },
                grid: { color: "#e7e9ee" },
              },
              yPrice: {
                display: showOverlay && hasOverlayData,
                position: "right",
                type: overlayLogScale ? "logarithmic" : "linear",
                ticks: { color: "#2c3e50" },
                grid: {
                  drawOnChartArea: false,
                },
              },
            },
            plugins: {
              legend: { display: showOverlay && hasOverlayData },
            },
          }}
        />
      </div>
    </section>
  );
}

function BreakdownPanel({
  title,
  payload,
  accent,
  overlayPayload,
  overlayColumn,
  overlayLabel,
  overlayLogScale = false,
}) {
  const columns = useMemo(() => listColumns(payload), [payload]);
  const preferred = useMemo(
    () => columns.find((name) => name.endsWith("_heat_contribution")) || columns[0] || "",
    [columns],
  );
  const [selectedColumn, setSelectedColumn] = useState(preferred);
  const [showOverlay, setShowOverlay] = useState(false);

  useEffect(() => {
    setSelectedColumn(preferred);
  }, [preferred]);

  const series = useMemo(
    () =>
      chartData(payload, selectedColumn, {
        overlayPayload,
        overlayColumn,
      }),
    [payload, selectedColumn, overlayPayload, overlayColumn],
  );
  const latestContributions = useMemo(() => pickLatestContributions(payload), [payload]);
  const hasOverlayData = series.overlayValues.some((value) => value !== null);
  const datasets = [
    {
      label: selectedColumn,
      data: series.values,
      borderColor: accent,
      borderWidth: 1.8,
      pointRadius: 0,
      fill: true,
      backgroundColor: `${accent}22`,
      tension: 0.2,
      yAxisID: "y",
    },
  ];

  if (showOverlay && hasOverlayData) {
    datasets.push({
      label: overlayLabel,
      data: series.overlayValues,
      borderColor: "#2c3e50",
      borderWidth: 1.5,
      pointRadius: 0,
      fill: false,
      tension: 0.15,
      yAxisID: "yPrice",
    });
  }

  return (
    <section className="panel">
      <div className="panel__header-row">
        <h3>{title}</h3>
        <div className="panel__controls">
          <label className="panel__overlay-toggle">
            <input
              type="checkbox"
              checked={showOverlay}
              onChange={(event) => setShowOverlay(event.target.checked)}
              disabled={!hasOverlayData}
            />
            {`Overlay ${overlayLabel}`}
          </label>
          <select
            aria-label={`${title} metric selector`}
            value={selectedColumn}
            onChange={(event) => setSelectedColumn(event.target.value)}
          >
            {columns.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="chart-wrap">
        <Line
          data={{
            labels: series.labels,
            datasets,
          }}
          options={{
            animation: false,
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              x: {
                ticks: { maxTicksLimit: 8, color: "#5a5c66" },
                grid: { color: "#e7e9ee" },
              },
              y: {
                ticks: { color: "#5a5c66" },
                grid: { color: "#e7e9ee" },
              },
              yPrice: {
                display: showOverlay && hasOverlayData,
                position: "right",
                type: overlayLogScale ? "logarithmic" : "linear",
                ticks: { color: "#2c3e50" },
                grid: {
                  drawOnChartArea: false,
                },
              },
            },
            plugins: {
              legend: { display: showOverlay && hasOverlayData },
            },
          }}
        />
      </div>

      <div className="table-grid">
        <h4>Latest Top Heat Contributions</h4>
        <table>
          <thead>
            <tr>
              <th>Signal</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            {latestContributions.length === 0 ? (
              <tr>
                <td colSpan={2}>No contribution data available.</td>
              </tr>
            ) : (
              latestContributions.map((item) => (
                <tr key={item.name}>
                  <td>{item.name}</td>
                  <td>{valueLabel(item.value, 4)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
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
  const sanityReport = Array.isArray(diagnostics?.sanity_report) ? diagnostics.sanity_report : [];
  const warnings = Array.isArray(diagnostics?.validation?.warnings) ? diagnostics.validation.warnings : [];

  return (
    <section className="panel diagnostics" aria-label="Diagnostics panel">
      <h3>Diagnostics</h3>

      <div className="diagnostics__warnings">
        <h4>Validation Warnings</h4>
        {warnings.length === 0 ? (
          <p>No validation warnings.</p>
        ) : (
          <ul>
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        )}
      </div>

      <div className="table-grid">
        <h4>Source Availability / Mode</h4>
        <table>
          <thead>
            <tr>
              <th>Source</th>
              <th>Available</th>
              <th>Mode</th>
              <th>Staleness (days)</th>
            </tr>
          </thead>
          <tbody>
            {sourceHealth.map((row) => (
              <tr key={row.source}>
                <td>{row.source}</td>
                <td>{row.available ? "yes" : "no"}</td>
                <td>{sourceModes.get(row.source) || "unknown"}</td>
                <td>{row.staleness_days ?? "n/a"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="table-grid">
        <h4>Sanity Report</h4>
        <table>
          <thead>
            <tr>
              <th>Check</th>
              <th>Passed</th>
              <th>Value</th>
              <th>Threshold</th>
            </tr>
          </thead>
          <tbody>
            {sanityReport.map((row) => (
              <tr key={row.check}>
                <td>{row.check}</td>
                <td>{row.passed ? "yes" : "no"}</td>
                <td>{row.value ?? "n/a"}</td>
                <td>{row.threshold ?? "n/a"}</td>
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
  const [error, setError] = useState("");
  const [payload, setPayload] = useState(null);
  const [showHeadlineOverlay, setShowHeadlineOverlay] = useState(false);

  useEffect(() => {
    let active = true;

    async function run() {
      try {
        const data = await loadDashboardData();
        if (!active) {
          return;
        }
        setPayload(data);
        setStatus("ready");
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Unknown data load error");
        setStatus("error");
      }
    }

    run();

    return () => {
      active = false;
    };
  }, []);

  if (status === "loading") {
    return <main className="page"><p className="status">Loading dashboard artifacts...</p></main>;
  }

  if (status === "error") {
    return (
      <main className="page">
        <p className="status status--error">Failed to load dashboard data: {error}</p>
      </main>
    );
  }

  const latest = payload.latestSnapshot;
  const degraded = payload.degraded;

  const heatSeries = chartData(payload.historyCore, "headline_direction", {
    overlayPayload: payload.historyCore,
    overlayColumn: "btc_price",
  });
  const attentionSeries = chartData(payload.historyCore, "headline_attention", {
    overlayPayload: payload.historyCore,
    overlayColumn: "btc_price",
  });
  const confidenceSeries = chartData(payload.historyCore, "confidence_score", {
    overlayPayload: payload.historyCore,
    overlayColumn: "btc_price",
  });

  return (
    <main className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">Risk Metric v1</p>
          <h1>Crypto Risk & Attention Dashboard</h1>
          <p className="subtext">Generated {payload.manifest.generated_at} from static contract artifacts.</p>
        </div>

        <div className="badges" aria-label="Degraded indicators">
          <span className="badge badge--stable">Schema {payload.manifest.schema_version}</span>
          {degraded.isDegraded ? (
            <>
              <span className="badge badge--degraded" data-testid="degraded-badge">
                Degraded data
              </span>
              {degraded.reasons.map((reason) => (
                <span key={reason} className="badge badge--warning">
                  {reason}
                </span>
              ))}
            </>
          ) : (
            <span className="badge badge--ok">No degraded-source flags</span>
          )}
        </div>
      </header>

      <section className="cards" aria-label="Latest cards">
        <StatCard label="BTC Risk Heat" value={valueLabel(latest.btc_risk?.heat)} tone="heat" />
        <StatCard label="BTC Risk Attention" value={valueLabel(latest.btc_risk?.attention)} tone="attention" />
        <StatCard label="Total Market Heat" value={valueLabel(latest.total_market_risk?.heat)} tone="heat" />
        <StatCard label="Total Market Attention" value={valueLabel(latest.total_market_risk?.attention)} tone="attention" />
        <StatCard label="Headline Attention" value={valueLabel(latest.headline_attention)} tone="attention" />
        <StatCard label="Headline Direction" value={valueLabel(latest.headline_direction)} tone="heat" />
        <StatCard label="Confidence Score" value={valueLabel(latest.confidence_score)} tone="confidence" />
      </section>

      <section className="grid grid--charts" aria-label="Core charts">
        <div className="section-controls">
          <label className="panel__overlay-toggle">
            <input
              type="checkbox"
              checked={showHeadlineOverlay}
              onChange={(event) => setShowHeadlineOverlay(event.target.checked)}
            />
            Overlay BTC Price (log)
          </label>
        </div>
        <TrendChart
          title="Headline Direction (Full History)"
          labels={heatSeries.labels}
          values={heatSeries.values}
          yBounds={[-1, 1]}
          color="#d0474f"
          showOverlay={showHeadlineOverlay}
          overlayValues={heatSeries.overlayValues}
          overlayLabel="BTC Price"
          overlayLogScale={true}
        />
        <TrendChart
          title="Headline Attention (Full History)"
          labels={attentionSeries.labels}
          values={attentionSeries.values}
          yBounds={[0, 1]}
          color="#0a8b9f"
          showOverlay={showHeadlineOverlay}
          overlayValues={attentionSeries.overlayValues}
          overlayLabel="BTC Price"
          overlayLogScale={true}
        />
        <TrendChart
          title="Confidence Score (Full History)"
          labels={confidenceSeries.labels}
          values={confidenceSeries.values}
          yBounds={[0, 1]}
          color="#1d6fd8"
          showOverlay={showHeadlineOverlay}
          overlayValues={confidenceSeries.overlayValues}
          overlayLabel="BTC Price"
          overlayLogScale={true}
        />
      </section>

      <section className="grid grid--breakdowns" aria-label="Category and metric breakdowns">
        <BreakdownPanel
          title="Category Breakdown - BTC"
          payload={payload.categoryBtc}
          accent="#c14953"
          overlayPayload={payload.historyCore}
          overlayColumn="btc_price"
          overlayLabel="BTC Price"
          overlayLogScale={true}
        />
        <BreakdownPanel
          title="Category Breakdown - Total Market"
          payload={payload.categoryTotal}
          accent="#6a6a44"
          overlayPayload={payload.historyCore}
          overlayColumn="total_market_cap"
          overlayLabel="Total Market Cap"
        />
        <BreakdownPanel
          title="Metric Breakdown - BTC"
          payload={payload.metricBtc}
          accent="#5e44b2"
          overlayPayload={payload.historyCore}
          overlayColumn="btc_price"
          overlayLabel="BTC Price"
          overlayLogScale={true}
        />
        <BreakdownPanel
          title="Metric Breakdown - Total Market"
          payload={payload.metricTotal}
          accent="#2f7f59"
          overlayPayload={payload.historyCore}
          overlayColumn="total_market_cap"
          overlayLabel="Total Market Cap"
        />
      </section>

      <DiagnosticsPanel diagnostics={payload.diagnostics} />
    </main>
  );
}
