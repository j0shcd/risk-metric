import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { forwardRef, useImperativeHandle } from "react";
import { vi } from "vitest";

import App, { PublicDataPanel } from "./App";
import { RISK_REGIONS } from "./data";
import { METRIC_COPY } from "./copy";
import { readFileSync } from "node:fs";
const styles = readFileSync(`${process.cwd()}/src/styles.css`, "utf8");
const charts = vi.hoisted(() => ({ props: [], reset: vi.fn() }));

vi.mock("react-chartjs-2", () => ({
  Line: forwardRef((props, ref) => {
    charts.props.push(props);
    useImperativeHandle(ref, () => ({ resetZoom: charts.reset }));
    return <canvas role={props.role} aria-label={props["aria-label"]} data-testid="chart" />;
  }),
}));

const baseColumnar = {
  release_id: "release-1",
  generated_at: "2026-04-24T06:00:00Z",
  schema_version: "2.0.0",
  version: "v2",
  index_name: "date",
  index: ["2026-04-22", "2026-04-23", "2026-04-24"],
  columns: {
    category_price_structure_signal_contribution: [0.1, 0.2, 0.3],
  },
};

const fixtures = {
  "manifest.json": {
    release_id: "release-1",
    version: "v2",
    schema_version: "2.0.0",
    generated_at: "2026-04-24T06:00:00Z",
    artifacts: [
      "manifest.json",
      "latest_snapshot.json",
      "history_core.json",
      "category_breakdowns_btc.json",
      "category_breakdowns_total_market.json",
      "metric_breakdowns_btc.json",
      "metric_breakdowns_total_market.json",
      "diagnostics.json",
    ],
  },
  "latest_snapshot.json": {
    release_id: "release-1",
    generated_at: "2026-04-24T06:00:00Z",
    schema_version: "2.0.0",
    version: "v2",
    date: "2026-04-24",
    btc_risk: { signal: 0.21, attention: 0.44, confidence: 0.62, coverage: 0.55 },
    total_market_risk: { signal: 0.16, attention: 0.39, confidence: 0.54, coverage: 0.48 },
    headline_attention: 0.42,
    trend_composite_score: 0.09,
    cycle_extension_score: 0.31,
    top_reversal_risk: 0.58,
    bottom_reversal_risk: 0.41,
    attention_score: 0.42,
    confidence_score: 0.58,
    cycle_model: {
      frenzy_score: 0.68,
      accumulation_score: 0.32,
      p_frenzy: 0.61,
      p_accumulation: 0.38,
      confidence: 0.74,
      position: 1,
      signal_regime: "HOLD",
    },
  },
  "history_core.json": {
    release_id: "release-1",
    generated_at: "2026-04-24T06:00:00Z",
    schema_version: "2.0.0",
    version: "v2",
    index_name: "date",
    index: ["2026-04-22", "2026-04-23", "2026-04-24"],
    columns: {
      trend_composite_score: [0.03, 0.07, 0.09],
      headline_attention: [0.34, 0.39, 0.42],
      cycle_extension_score: [0.24, 0.28, 0.31],
      top_reversal_risk: [0.45, 0.51, 0.58],
      bottom_reversal_risk: [0.52, 0.48, 0.41],
      attention_score: [0.31, 0.37, 0.42],
      confidence_score: [0.6, 0.59, 0.58],
      cycle_frenzy_score: [0.58, 0.63, 0.68],
      cycle_confidence: [0.72, 0.73, 0.74],
      btc_price: [62000, 63500, 64000],
      total_market_cap: [2.1e12, 2.12e12, 2.15e12],
    },
  },
  "metric_breakdowns_btc.json": {
    ...baseColumnar,
    columns: {
      metric_a_signal_contribution: [0.12, 0.13, 0.14],
      metric_b_signal_contribution: [-0.05, -0.06, -0.07],
      metric_btc_trend_extension_50d_350d__btc__price_structure_signal: [0.21, 0.24, 0.28],
    },
  },
  "diagnostics.json": {
    release_id: "release-1",
    generated_at: "2026-04-24T06:00:00Z",
    schema_version: "2.0.0",
    version: "v2",
    validation: {
      passed: true,
      errors: [],
      warnings: ["Some sources are unavailable."],
    },
    source_modes: [
      { source: "btc_price", mode: "local_csv" },
      { source: "social::youtube_interest", mode: "unavailable" },
    ],
    source_health: [
      { source: "btc_price", available: true, staleness_days: 0 },
      { source: "social::youtube_interest", available: false, staleness_days: null },
    ],
    metric_health: [],
    sanity_report: [{ check: "example", passed: true, value: 1.0, threshold: 0.0 }],
  },
};

describe("App", () => {
  beforeEach(() => {
    charts.props.length = 0;
    charts.reset.mockClear();
    window.localStorage.clear();
    window.history.replaceState(null, "", "/");
    global.fetch = vi.fn(async (url) => {
      const key = String(url).split("/").pop();
      if (!key || !(key in fixtures)) {
        return { ok: false, status: 404, json: async () => ({}) };
      }
      return {
        ok: true,
        status: 200,
        json: async () => fixtures[key],
      };
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    delete Element.prototype.scrollIntoView;
  });

  function useHistory(history) {
    const originalFetch = global.fetch;
    global.fetch = vi.fn(async (url) => String(url).endsWith("history_core.json")
      ? { ok: true, json: async () => ({ ...fixtures["history_core.json"], ...history }) }
      : originalFetch(url));
  }

  it("omits a missing driver when three finite components permit publication", async () => {
    useHistory({ columns: {
      dca_risk: [0.2, 0.3, 0.4], dca_component_coverage: [1, 1, 0.75],
      dca_top_reversal_component: [0.2, 0.3, 0.4], dca_bottom_reversal_component: [0.2, 0.3, 0.5],
      dca_cycle_extension_component: [0.2, 0.3, null], dca_cycle_regime_component: [0.2, 0.3, 0.6],
    } });
    render(<App />);
    await screen.findByText("What is moving it");
    const drivers = document.querySelector(".bb-drivers__list");
    expect(within(drivers).getAllByRole("listitem")).toHaveLength(3);
    expect(within(drivers).queryByText("Price stretch")).not.toBeInTheDocument();
    expect(within(drivers).getAllByRole("listitem").map((row) => row.textContent)).toEqual([
      "Speculation and hype60", "Unlike past bottoms50", "Looks like past peaks40",
    ]);
  });

  it("uses shared display ranges and explains unrounded boundaries", async () => {
    expect(RISK_REGIONS.map((entry) => entry.displayRange)).toEqual(["0 to 25", "25 to 75", "75 to 100"]);
    const region = RISK_REGIONS[1];
    const original = region.displayRange;
    try {
      region.displayRange = "shared range sentinel";
      render(<App />);
      expect(await screen.findByRole("cell", { name: region.displayRange })).toBeInTheDocument();
      for (const entry of RISK_REGIONS) expect(screen.getByRole("cell", { name: entry.displayRange })).toBeInTheDocument();
      expect(screen.getByText(/Shares count every day since .* Boundaries use the unrounded score, so exactly 25 counts as Low and exactly 75 as High\./)).toBeInTheDocument();
    } finally {
      region.displayRange = original;
    }
  });

  it("names the last published reading when the newest finite reading lacks coverage", async () => {
    useHistory({ index: ["2026-04-23", "2026-04-24"], columns: {
      dca_risk: [0.2, 0.8], dca_component_coverage: [1, 0.5],
    } });
    render(<App />);
    expect(await screen.findByRole("heading", { name: "No reading today" })).toBeInTheDocument();
    expect(screen.getByText("The last published reading was 20 on 23 Apr 2026.")).toBeInTheDocument();
  });

  it("opens and scrolls Today for #data instead of the saved Method tab", async () => {
    window.localStorage.setItem("riskMetricActiveTab.v1", "method");
    window.history.replaceState(null, "", "/#data");
    const scroll = vi.fn();
    Object.defineProperty(Element.prototype, "scrollIntoView", { configurable: true, value: scroll });
    render(<App />);
    expect(await screen.findByRole("heading", { name: "How heated does the Bitcoin market look today?" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Today" })).toHaveAttribute("aria-current", "page");
    expect(scroll).toHaveBeenCalled();
    expect(scroll.mock.instances.at(-1)).toBe(document.getElementById("data"));
    fireEvent.click(screen.getByRole("button", { name: "Method" }));
    expect(await screen.findByText("The four sub-scores")).toBeInTheDocument();
    window.history.replaceState(null, "", "/");
    window.history.replaceState(null, "", "/#data");
    window.dispatchEvent(new Event("hashchange"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Today" })).toHaveAttribute("aria-current", "page"));
    expect(scroll.mock.instances.at(-1)).toBe(document.getElementById("data"));
  });

  it("preserves overview defaults, legend order and all dataset styles when toggled", async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Method" }));
    const switches = within(screen.getByRole("group", { name: "Series visibility" })).getAllByRole("switch");
    expect(switches.map((item) => item.getAttribute("aria-label"))).toEqual([
      "Looks like past peaks — shown", "Looks like past bottoms — shown", "Price stretch — hidden",
      "Speculation and hype — hidden", "Signals agreeing (context) — hidden",
    ]);
    expect(switches[4]).toHaveClass("bb-legend__item--context");
    const overview = () => charts.props.findLast((props) => props["aria-label"]?.startsWith("Sub-scores"));
    expect(overview().data.datasets.map((item) => item.label)).toEqual(["Looks like past peaks", "Looks like past bottoms", "BTC price"]);
    for (const item of switches.slice(2)) fireEvent.click(item);
    const datasets = overview().data.datasets;
    expect(datasets.map((item) => [item.label, item.borderColor, item.backgroundColor, item.tension])).toEqual([
      ["Looks like past peaks", "#f05b5b", "#f05b5b1f", 0.16],
      ["Looks like past bottoms", "#22cc55", "#22cc5517", 0.16],
      ["Price stretch", "#f0a500", "#f0a50019", 0.16],
      ["Signals agreeing", "#5ca2ff", "#5ca2ff19", 0.16],
      ["Speculation and hype", "#b58cff", "#b58cff19", 0.14],
      ["BTC price", "#8b8473", undefined, 0.12],
    ]);
    const columns = fixtures["history_core.json"].columns;
    expect(datasets.map((item) => item.data)).toEqual([
      columns.top_reversal_risk, columns.bottom_reversal_risk, columns.cycle_extension_score,
      columns.attention_score, columns.cycle_frenzy_score, columns.btc_price,
    ]);
    expect(datasets.at(-1).yAxisID).toBe("yPrice");
  });

  it("leads with the reading and its context, then switches tabs", async () => {
    render(<App />);

    expect(await screen.findByText("How heated does the Bitcoin market look today?")).toBeInTheDocument();
    expect(screen.getByText(/Recent reading|days behind/)).toBeInTheDocument();
    expect(screen.queryByText("Updated daily")).not.toBeInTheDocument();
    expect(screen.getByText(/Higher than \d+% of days since/)).toBeInTheDocument();
    expect(screen.getByText("Risk against price")).toBeInTheDocument();
    expect(screen.getByText("you are here")).toBeInTheDocument();
    expect(screen.getByText("What is moving it")).toBeInTheDocument();
    const navigation = within(screen.getByRole("navigation", { name: "Primary" }));
    expect(navigation.getAllByRole("button").map((tab) => tab.textContent)).toEqual([
      "Today", "Track record", "Method",
    ]);
    expect(screen.getByText("Looks like past peaks")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Method" }));

    expect(await screen.findByText("The four sub-scores")).toBeInTheDocument();
    expect(screen.getByText(/How the reading is built/i)).toBeInTheDocument();
    expect(screen.getByText("MVRV Ratio Z Proxy")).toBeInTheDocument();
    expect(screen.getByText(/Display only — excluded from scoring/i)).toBeInTheDocument();
    expect(screen.getByText("Each line is that sub-score on its 0 to 100 scale. The sections below explain how each one is built. Series start in December 2014.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Track record" }));
    expect(await screen.findByRole("heading", { name: "Did waiting to buy help?" })).toBeInTheDocument();
  });

  it("surfaces validation failures from diagnostics", async () => {
    global.fetch = vi.fn(async (url) => {
      const key = String(url).split("/").pop();
      if (!key || !(key in fixtures)) {
        return { ok: false, status: 404, json: async () => ({}) };
      }
      if (key === "diagnostics.json") {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            ...fixtures["diagnostics.json"],
            validation: {
              passed: false,
              errors: ["Critical source contract failed: btc_price(stale:17d>3d)"],
              warnings: [],
            },
            source_health: [
              {
                source: "btc_price",
                available: true,
                contract_passed: 0,
                contract_issues: "stale:17d>3d",
                staleness_days: 17,
              },
            ],
          }),
        };
      }
      return {
        ok: true,
        status: 200,
        json: async () => fixtures[key],
      };
    });

    render(<App />);

    expect(await screen.findByText("Data check needed")).toBeInTheDocument();
    expect(screen.queryByLabelText(/Data status/i)).not.toBeInTheDocument();
  });

  it("renders even when diagnostics payload is minimal", async () => {
    global.fetch = vi.fn(async (url) => {
      const key = String(url).split("/").pop();
      if (!key || !(key in fixtures)) {
        return { ok: false, status: 404, json: async () => ({}) };
      }
      if (key === "diagnostics.json") {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            release_id: "release-1",
            generated_at: "2026-04-24T06:00:00Z",
            schema_version: "2.0.0",
            version: "v2",
            validation: { passed: true, errors: [], warnings: [] },
            source_modes: [],
            source_health: [],
            metric_health: [],
            sanity_report: [],
          }),
        };
      }
      return {
        ok: true,
        status: 200,
        json: async () => fixtures[key],
      };
    });

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Method" }));

    expect((await screen.findAllByText("Trend Extension (50d/350d)")).length).toBeGreaterThan(0);
  });
  it("renders Today when storage reads and writes throw", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    render(<App />);
    expect(await screen.findByRole("heading", { level: 1, name: "How heated does the Bitcoin market look today?" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Today" })).toHaveAttribute("aria-current", "page");
  });

  it.each([true, false])("explains a degraded reading, with prior reading available: %s", async (hasPrior) => {
    const history = fixtures["history_core.json"];
    const fetchOriginal = global.fetch;
    global.fetch = vi.fn(async (url) => String(url).endsWith("history_core.json") ? {
      ok: true, json: async () => ({ ...history, columns: { dca_risk: hasPrior ? [0.19, null, null] : [null, null, null], dca_component_coverage: [1, 1, 1] } }),
    } : fetchOriginal(url));
    render(<App />);
    expect(await screen.findByRole("heading", { level: 1, name: "No reading today" })).toBeInTheDocument();
    expect(screen.getByText("Too many of the underlying sources are missing to publish a number. It comes back once they recover.")).toBeInTheDocument();
    if (hasPrior) expect(screen.getByText("The last published reading was 19 on 22 Apr 2026.")).toBeInTheDocument();
    else expect(screen.queryByText(/The last published reading/)).not.toBeInTheDocument();
    expect(screen.queryByText(/on the chart under Method/)).not.toBeInTheDocument();
    // The JSON docs (and the /#data target) stay reachable on a day with no reading.
    expect(document.getElementById("data")).toBeInTheDocument();
    expect(screen.getByText(/api\/v1\/latest\.json/)).toBeInTheDocument();
  });

  it("keeps region descriptions muted and left aligned, and technical values scoped", async () => {
    const style = document.createElement("style");
    style.textContent = styles;
    document.head.appendChild(style);
    try {
      render(<App />);
      const desc = await screen.findByText("Quiet, well below the peaks of past cycles.");
      expect(getComputedStyle(desc).textAlign).toBe("left");
      expect(styles).not.toMatch(/\.bb-table td:last-child\s*\{/);
      expect(styles).toMatch(/\.bb-table--technical td:last-child\s*\{/);
      expect(screen.getByText("Share of days")).toBeInTheDocument();
      expect(screen.getByText(/Shares count every day since/)).toBeInTheDocument();
      expect(styles).toMatch(/\.bb-regions tr\s*\{[^}]*display: block/);
    } finally { style.remove(); }
  });

  it("loads raw inputs only on Method, shows loading, and caches across tab switches", async () => {
    let resolveMethod;
    const fetchOriginal = global.fetch;
    global.fetch = vi.fn((url) => String(url).endsWith("metric_breakdowns_btc.json")
      ? new Promise((resolve) => { resolveMethod = () => resolve({ ok: true, json: async () => fixtures["metric_breakdowns_btc.json"] }); })
      : fetchOriginal(url));
    render(<App />);
    await screen.findByRole("heading", { level: 1 });
    expect(global.fetch).toHaveBeenCalledTimes(4);
    fireEvent.click(screen.getByRole("button", { name: "Method" }));
    expect(await screen.findByText("Loading the raw inputs…")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(document.querySelectorAll(".bb-card-grid .bb-card")).toHaveLength(4);
    expect(screen.getByRole("heading", { name: "Context, not part of the reading" })).toBeInTheDocument();
    resolveMethod();
    expect(await screen.findByLabelText("Raw input")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Today" }));
    fireEvent.click(screen.getByRole("button", { name: "Method" }));
    expect(global.fetch.mock.calls.filter(([url]) => String(url).endsWith("metric_breakdowns_btc.json"))).toHaveLength(1);
  });

  it("renders Method immediately even when raw inputs fail", async () => {
    const fetchOriginal = global.fetch;
    global.fetch = vi.fn(async (url) => String(url).endsWith("metric_breakdowns_btc.json") ? { ok: false, status: 503 } : fetchOriginal(url));
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Method" }));
    expect(await screen.findByText("The raw inputs did not load. Reload to try again.")).toBeInTheDocument();
    expect(screen.getByText("The four sub-scores over time")).toBeInTheDocument();
  });

  it("uses whole score ticks and tooltips, ctrl-wheel zoom, named canvases and range reset", async () => {
    render(<App />);
    await screen.findByRole("img", { name: /Risk reading and Bitcoin price/ });
    const risk = charts.props.at(-1);
    expect([0, .25, .5, .75, 1].map(risk.options.scales.y.ticks.callback)).toEqual(["0", "25", "50", "75", "100"]);
    expect(risk.options.scales.y.ticks.stepSize).toBe(.25);
    expect(risk.options.plugins.tooltip.callbacks.label({ dataset: { label: "Risk" }, parsed: { y: .191 } })).toBe("Risk: 19");
    expect(risk.options.plugins.zoom.zoom.wheel).toEqual({ enabled: true, modifierKey: "ctrl" });
    expect(risk.data.datasets.find((d) => d.label === "Low, 25").data.every((v) => v === .25)).toBe(true);
    expect(risk.data.datasets.find((d) => d.label === "High, 75").data.every((v) => v === .75)).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "All" }));
    expect(charts.reset).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole("button", { name: "Method" }));
    await screen.findByLabelText("Raw input");
    const overview = charts.props.findLast((props) => props["aria-label"]?.startsWith("Sub-scores"));
    expect(overview.options.scales.y.ticks.callback(.75)).toBe("75");
    expect(overview.options.plugins.tooltip.callbacks.label({ dataset: { label: "Price stretch" }, parsed: { y: .31 } })).toBe("Price stretch: 31");
    expect(Array.from(document.querySelectorAll(".bb-card__value")).map((card) => card.textContent)).toEqual(["58", "41", "31", "68"]);
    const raw = charts.props.at(-1);
    expect(raw.options.scales.y).not.toHaveProperty("min");
    expect(raw.options.scales.y.ticks).not.toHaveProperty("callback");
    expect(screen.getByRole("img", { name: /Sub-scores over time, shown:/ })).toBeInTheDocument();
  });

  it("shares compact price axes and responsive unrotated date ticks across all charts", async () => {
    render(<App />);
    await screen.findByRole("img", { name: /Risk reading and Bitcoin price/ });
    const risk = charts.props.at(-1);
    fireEvent.click(screen.getByRole("button", { name: "Method" }));
    await screen.findByLabelText("Raw input");
    const overview = charts.props.findLast((props) => props["aria-label"]?.startsWith("Sub-scores"));
    const raw = charts.props.at(-1);
    for (const { options } of [risk, overview, raw]) {
      const priceTicks = options.scales.yPrice.ticks;
      expect(priceTicks.callback(100000)).toBe("100k");
      expect(priceTicks.callback(59000)).toBe("");
      expect(priceTicks.maxTicksLimit).toBe(6);
      expect(priceTicks.autoSkip).toBe(true);
      expect(priceTicks.autoSkipPadding).toBeGreaterThanOrEqual(12);
      const dateTicks = options.scales.x.ticks;
      expect(dateTicks.maxRotation).toBe(0);
      expect(dateTicks.autoSkip).toBe(true);
      // Chart.js does not resolve a scriptable maxTicksLimit; label width plus
      // padding is what thins dates on narrow charts.
      expect(dateTicks.maxTicksLimit).toBe(8);
      expect(dateTicks.autoSkipPadding).toBeGreaterThanOrEqual(24);
      expect(dateTicks.callback.call({ getLabelForValue: () => "2024-11-05" }, 0)).toBe("Nov 2024");
      expect(options.plugins.tooltip.callbacks.title([{ label: "2024-11-05" }])).toBe("Date: 2024-11-05");
      expect(options.plugins.tooltip.callbacks.label({ dataset: { label: "BTC", yAxisID: "yPrice" }, parsed: { y: 59000 } })).toBe("BTC: 59,000");
    }
    fireEvent.change(screen.getAllByLabelText("Price scale").at(-1), { target: { value: "linear" } });
    expect(charts.props.at(-1).options.scales.yPrice.type).toBe("linear");
    expect(charts.props.at(-1).options.scales.yPrice.ticks.callback(59000)).toBe("59k");
  });

  it("gives the calculation its own named section outside the sub-scores", async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Method" }));
    const calculation = screen.getByRole("region", { name: "The calculation, step by step" });
    expect(calculation.querySelectorAll("ol li")).toHaveLength(METRIC_COPY.scoring.steps.length);
    expect(calculation).not.toContainElement(screen.getByRole("heading", { name: "The four sub-scores" }));
    expect(calculation.previousElementSibling).toContainElement(screen.getByRole("heading", { name: "The four sub-scores" }));
  });

  it("keeps legacy names out of reader-facing metric copy", () => {
    for (const copy of Object.values(METRIC_COPY)) {
      for (const field of ["shortName", "description", "oneLiner", "notMeaning"]) {
        expect(copy[field] ?? "").not.toMatch(/Cycle Extension|Top Reversal Risk|Bottom Reversal Risk|Signal Agreement|Cycle Frenzy|dca_risk|DCA Risk/i);
      }
    }
  });

  it("keeps the CSS type floor, keyboard focus and steady reduced-motion cursor", () => {
    const sizes = Array.from(styles.matchAll(/font-size:\s*(0\.\d+)rem/g), (match) => Number(match[1]));
    expect(sizes.length).toBeGreaterThan(20);
    expect(Math.min(...sizes)).toBeGreaterThanOrEqual(.75);
    expect(styles).toMatch(/:where\(button, a, select, input, summary\):focus-visible/);
    expect(styles).toMatch(/\.bb-dca-warning\s*\{[^}]*color: var\(--bb-red\)/);
    expect(styles).toMatch(/\.bb-research,\s*\.bb-blink\s*\{ animation: none; \}/);
  });

});

describe("PublicDataPanel", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: undefined });
    window.getSelection()?.removeAllRanges();
  });

  it("renders both absolute URLs as links", () => {
    render(<PublicDataPanel />);
    expect(screen.getByRole("heading", { name: "Use the numbers yourself" })).toBeInTheDocument();
    for (const file of ["latest", "history"]) {
      const url = `${window.location.origin}/api/v1/${file}.json`;
      expect(screen.getByRole("link", { name: url })).toHaveAttribute("href", url);
    }
  });

  it("copies the right URL and resets the success label after two seconds", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    render(<PublicDataPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Copy Today URL" }));
    await screen.findByRole("button", { name: "Copied Today URL" });
    expect(writeText).toHaveBeenLastCalledWith(`${window.location.origin}/api/v1/latest.json`);
    await waitFor(() => expect(screen.getByRole("button", { name: "Copy Today URL" })).toBeInTheDocument(), { timeout: 2500 });
    fireEvent.click(screen.getByRole("button", { name: "Copy Every day since 2014 URL" }));
    await screen.findByRole("button", { name: "Copied Every day since 2014 URL" });
    expect(writeText).toHaveBeenLastCalledWith(`${window.location.origin}/api/v1/history.json`);
  });

  it.each([undefined, { writeText: vi.fn().mockRejectedValue(new Error("denied")) }])("selects the URL without throwing if clipboard fails (%s)", async (clipboard) => {
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: clipboard });
    render(<PublicDataPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Copy Today URL" }));
    await waitFor(() => expect(window.getSelection().toString()).toBe(`${window.location.origin}/api/v1/latest.json`));
    expect(screen.getByRole("button", { name: "Copy Today URL" })).toHaveTextContent("Copy");
  });
});
