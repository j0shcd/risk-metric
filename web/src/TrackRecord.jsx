import { useState } from "react";
import { compareDca, DCA_EVIDENCE, DCA_PERIODS } from "./dcaEvidence";

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
const month = new Intl.DateTimeFormat("en-US", { month: "short", year: "numeric", timeZone: "UTC" });
const day = new Intl.DateTimeFormat("en-US", { month: "long", day: "numeric", year: "numeric", timeZone: "UTC" });
const btc = new Intl.NumberFormat("en-US", { minimumFractionDigits: 8, maximumFractionDigits: 8 });
const monthLabel = (date) => month.format(new Date(`${date}T00:00:00Z`));
const percent = (value) => `${Math.abs(value*100).toFixed(2)}%`;

export default function TrackRecord() {
  const [start, setStart] = useState(DCA_PERIODS.at(-1).start);
  const [amount, setAmount] = useState("100");
  const period = DCA_PERIODS.find((item) => item.start === start);
  const result = compareDca(period, amount);
  const maximum = Math.max(period.fixedBtc, period.scoreBtc);
  const summary = DCA_EVIDENCE.summary;
  const warmup = DCA_EVIDENCE.comparisons.find((row) => row.arm === "warmup_matched_incumbent");
  const components = DCA_EVIDENCE.comparisons.find((row) => row.arm === "gaussian_components");
  return (
    <section className="bb-research" aria-labelledby="track-record-title">
      <header className="bb-record-intro">
        <h1 id="track-record-title">Did waiting to buy help?</h1>
        <p>Across {summary.count} four-year historical periods, score-based buying accumulated a median <strong>{percent(summary.median)} less BTC</strong> than fixed monthly buying. It finished ahead in {summary.wins} periods.</p>
        <dl className="bb-record-meta">
          <div><dt>Last evaluated</dt><dd>{day.format(new Date(`${DCA_EVIDENCE.evaluatedAt}T00:00:00Z`))}</dd></div>
          <div><dt>Data through</dt><dd>{day.format(new Date(`${DCA_PERIODS.at(-1).end}T00:00:00Z`))}</dd></div>
          <div><dt>Evidence type</dt><dd>{DCA_EVIDENCE.evidenceTier}</dd></div>
        </dl>
      </header>
      <section className="bb-dca-comparison" aria-labelledby="comparison-title">
        <h2 id="comparison-title">Same budget. Same four years.</h2>
        <div className="bb-dca-controls">
          <label>Historical period
            <select value={start} onChange={(event) => setStart(event.target.value)}>
              {DCA_PERIODS.toReversed().map((item) => <option key={item.start} value={item.start}>{monthLabel(item.start)} – {monthLabel(item.end)}</option>)}
            </select>
          </label>
          <label>Monthly contribution (USD)
            <input type="number" min="0.01" max="1000000" step="0.01" inputMode="decimal" value={amount}
              aria-invalid={!result} aria-describedby={!result ? "amount-error" : undefined}
              onChange={(event) => setAmount(event.target.value)} />
          </label>
        </div>
        {result ? <div aria-live="polite" aria-atomic="true">
          <p className="bb-dca-budget">Both strategies spend <strong>{usd.format(result.total)}</strong> over 48 monthly contributions.</p>
          <div className="bb-dca-results" role="group" aria-label="Selected period results">
            {[
              { name: "Fixed monthly buying", units: result.fixedBtc, value: result.fixedValue, fraction: period.fixedBtc/maximum, kind: "fixed" },
              { name: "Score-based buying", units: result.scoreBtc, value: result.scoreValue, fraction: period.scoreBtc/maximum, kind: "score" },
            ].map((row) => <div className={`bb-dca-result bb-dca-result--${row.kind}`} key={row.name}>
              <div className="bb-dca-result__heading"><h3>{row.name}</h3><p>{btc.format(row.units)} <span>BTC</span></p></div>
              <div className="bb-dca-bar" aria-hidden="true"><span style={{ width: `${row.fraction*100}%` }} /></div>
              <p className="bb-dca-value">Worth {usd.format(row.value)} at the {monthLabel(period.end)} close</p>
            </div>)}
          </div>
          <p className={`bb-dca-difference ${period.delta < 0 ? "bb-card__value--red" : "bb-card__value--green"}`}>
            Score-based buying accumulated <strong>{percent(period.delta)} {period.delta < 0 ? "less" : "more"} BTC</strong> in this period.
          </p>
          <p className="bb-dca-wait">Its contribution money waited an average of {period.waitMonths.toFixed(1)} months in cash; fixed monthly buying invested each contribution immediately. The final-date catch-up purchase was {usd.format(result.finalBuy)}.</p>
        </div> : <p className="bb-dca-input-error" id="amount-error" role="alert">Enter $0.01 to $1,000,000, with up to two decimal places.</p>}
        <p className="bb-dca-assumptions">Both receive the same monthly deposits and spend the full budget by the final close, including any catch-up purchase. Trades use month-end prices. Purchase costs are 0.20%; cash earns no interest. No selling or borrowing. Score-based decisions use the previous month’s reading.</p>
      </section>
      <p className="bb-record-limit">These 96 periods overlap and use history already studied. They are not 96 independent trials, live results or forecasts. Changing the amount scales the same historical trades; it does not rerun or improve the model.</p>
      <details className="bb-record-details">
        <summary>Other comparisons and research limits</summary>
        <p>The November 10 study also tested a six-month target and new forecast readouts. None of its seven new forecasters beat fixed monthly buying at the historical median. These experimental variants have not been adopted as production models.</p>
        <div className="bb-research-table-wrap">
          <table className="bb-research-table">
            <thead><tr><th scope="col">Buying rule</th><th scope="col">Median vs Fixed DCA</th><th scope="col">Periods ahead</th></tr></thead>
            <tbody>{DCA_EVIDENCE.comparisons.map((row) => <tr key={row.arm}>
              <th scope="row">{row.label}</th>
              <td data-label="Median vs Fixed DCA">{row.median < 0 ? "−" : "+"}{percent(row.median)}</td>
              <td data-label="Periods ahead">{row.wins}/{row.count}</td>
            </tr>)}</tbody>
          </table>
        </div>
        <p>The matched warm-up control buys regularly until training is possible, then uses the original score. Its {percent(warmup.median)} median shortfall was smaller than the four-component forecaster’s {percent(components.median)} shortfall. The six-month cash limit is a separate policy; a six-month training target does not impose that deadline.</p>
        <p>Forecast uncertainty remains poorly calibrated. Legacy input release dates are incompletely verified, so this is a reconstructed history, not proof that every input was available in real time.</p>
        <p>Older selling experiments started with one BTC and answered a different question. They do not establish a dependable selling signal and are excluded from this equal-budget buying comparison.</p>
        <a className="bb-link" href="https://github.com/j0shcd/risk-metric/blob/main/docs/dca_evidence.md">Full evidence and methodology</a>
      </details>
    </section>
  );
}
