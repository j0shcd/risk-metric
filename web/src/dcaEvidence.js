import windowsCsv from "../../docs/artifacts/target-readout-2026-11-10/market_windows.csv?raw";
import inputsCsv from "../../docs/artifacts/target-readout-2026-11-10/market_inputs.csv?raw";

// Frozen producer CSVs contain only unquoted names, dates and numbers.
function records(csv) {
  const [header, ...lines] = csv.trim().split(/\r?\n/).map((line) => line.split(","));
  return lines.map((values) => Object.fromEntries(header.map((key, i) => [key, values[i]])));
}
const windows = records(windowsCsv);
const prices = new Map(records(inputsCsv).map((row) => [row.date, Number(row.price)]));
const labels = {
  incumbent: "Score-based buying",
  incumbent_capped6: "Score-based buying, six-month cash limit",
  warmup_matched_incumbent: "Score-based buying, matched regular-buying warm-up",
  empirical_latest24: "Six-month target, empirical latest-24",
  empirical_split24: "Six-month target, empirical split-24",
  gaussian_split24: "Six-month target, Gaussian split-24",
  gaussian_expanding: "Six-month target, Gaussian expanding composite",
  gaussian_components: "Six-month target, Gaussian four components",
  gaussian_price_only: "Six-month target, Gaussian price-only",
  gaussian_pooled: "Six-month target, Gaussian pooled",
};

export const DCA_PERIODS = windows.filter((row) => row.arm === "incumbent").map((row) => ({
  start: row.start_date, end: row.end_date,
  fixedBtc: Number(row.fixed_btc_units), scoreBtc: Number(row.btc_units),
  delta: Number(row.delta_vs_fixed), waitMonths: Number(row.mean_wait_months),
  sweepShare: Number(row.terminal_sweep_share), endPrice: prices.get(row.end_date),
}));
function summarize(arm) {
  const values = windows.filter((row) => row.arm === arm).map((row) => Number(row.delta_vs_fixed)).sort((a, b) => a-b);
  const middle = Math.floor(values.length/2);
  return { arm, label: labels[arm], median: values.length % 2 ? values[middle] : (values[middle-1]+values[middle])/2,
    wins: values.filter((value) => value > 1e-12).length, count: values.length };
}
export const DCA_EVIDENCE = {
  evaluatedAt: "2026-11-10", evidenceTier: "Retrospective reconstruction",
  summary: summarize("incumbent"), comparisons: Object.keys(labels).map(summarize),
};
export function compareDca(period, monthlyAmount) {
  const amount = Number(monthlyAmount);
  if (String(monthlyAmount).trim() === "" || !Number.isFinite(amount) || amount < .01 || amount > 1_000_000
      || Math.abs(amount*100-Math.round(amount*100)) > 1e-6) return null;
  return { total: amount*48, fixedBtc: period.fixedBtc*amount, scoreBtc: period.scoreBtc*amount,
    fixedValue: period.fixedBtc*amount*period.endPrice, scoreValue: period.scoreBtc*amount*period.endPrice,
    finalBuy: period.sweepShare*amount*48 };
}
