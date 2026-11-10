import { describe, expect, it } from "vitest";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { compareDca, DCA_EVIDENCE, DCA_PERIODS } from "./dcaEvidence";

const root = resolve(process.cwd(), "../docs/artifacts/target-readout-2026-11-10");
const report = JSON.parse(readFileSync(resolve(root, "summary.json"), "utf8"));
const parse = (name) => {
  const [header, ...rows] = readFileSync(resolve(root, name), "utf8").trim().split(/\r?\n/).map((line) => line.split(","));
  return rows.map((values) => Object.fromEntries(header.map((key, i) => [key, values[i]])));
};

describe("equal-budget evidence", () => {
  it("uses the existing verified evidence bytes, without a replacement snapshot", () => {
    for (const name of ["market_inputs.csv", "market_windows.csv"]) {
      expect(createHash("sha256").update(readFileSync(resolve(root, name))).digest("hex")).toBe(report.output_sha256[name]);
    }
  });

  it("reconciles all 96 periods against a separate previous-month cash ledger", () => {
    const input = parse("market_inputs.csv");
    expect(DCA_PERIODS).toHaveLength(96);
    expect(new Set(DCA_PERIODS.map((p) => p.start)).size).toBe(96);
    for (const period of DCA_PERIODS) {
      const start = input.findIndex((row) => row.date === period.start);
      const rows = input.slice(start, start+48);
      expect(rows.at(-1).date).toBe(period.end);
      let cash = 0, units = 0, fixed = 0, waiting = 0, sweep = 0;
      for (let i = 0; i < 48; i++) {
        cash += 1;
        const risk = start+i > 0 ? Number(input[start+i-1].dca_risk) : NaN;
        const request = risk < .25 ? 1+2*(1-4*risk) : 0;
        let buy = Math.min(cash, request);
        if (i === 47) { sweep = cash-buy; buy = cash; }
        cash -= buy;
        units += buy*.998/Number(rows[i].price);
        fixed += .998/Number(rows[i].price);
        waiting += cash;
        expect(cash).toBeGreaterThanOrEqual(-1e-10);
      }
      expect(cash).toBe(0);
      expect(period.scoreBtc).toBeCloseTo(units, 12);
      expect(period.fixedBtc).toBeCloseTo(fixed, 12);
      expect(period.waitMonths).toBeCloseTo(waiting/48, 10);
      expect(period.sweepShare).toBeCloseTo(sweep/48, 10);
      expect(period.endPrice).toBe(Number(rows.at(-1).price));
      const result = compareDca(period, 100);
      expect(result.total).toBe(4800);
      expect(result.scoreBtc).toBeCloseTo(units*100, 10);
      expect(result.fixedBtc).toBeCloseTo(fixed*100, 10);
      expect(result.scoreValue/result.fixedValue-1).toBeCloseTo(period.delta, 12);
    }
  });

  it("derives every displayed median and win count from the registered comparisons", () => {
    for (const row of DCA_EVIDENCE.comparisons) {
      const expected = report.market.summary.find((r) => r.arm === row.arm);
      expect(row.median).toBeCloseTo(expected.median_delta, 12);
      expect(row.wins).toBe(expected.wins);
      expect(row.count).toBe(96);
    }
    expect(DCA_EVIDENCE.summary.wins).toBe(23);
  });

  it("scales every monetary outcome without applying purchase costs again", () => {
    const period = DCA_PERIODS.at(-1);
    const one = compareDca(period, 1), many = compareDca(period, 250.25);
    for (const key of Object.keys(one)) expect(many[key]).toBeCloseTo(one[key]*250.25, 8);
    expect(one.fixedBtc).toBe(period.fixedBtc);
    expect(one.fixedValue).toBe(period.fixedBtc*period.endPrice);
  });

  it("rejects empty, nonfinite, out-of-range and fractional-cent amounts", () => {
    for (const amount of ["", " ", "abc", 0, -1, Infinity, NaN, .001, 1.001, 1_000_001]) {
      expect(compareDca(DCA_PERIODS[0], amount), String(amount)).toBeNull();
    }
    for (const amount of [.01, 12.34, 1_000_000]) expect(compareDca(DCA_PERIODS[0], amount)).not.toBeNull();
  });
});
