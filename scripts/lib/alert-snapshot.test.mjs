import assert from "node:assert/strict";
import test from "node:test";
import { validateSnapshot } from "./alert-snapshot.mjs";

const now = new Date("2026-07-15T06:00:00Z");

test("validateSnapshot allows the two-day freshness boundary", () => {
  assert.deepEqual(validateSnapshot({ date: "2026-07-13", dca_risk: 0.25 }, now), {
    date: "2026-07-13",
    risk: 0.25,
  });
});

test("validateSnapshot rejects stale daily alert data", () => {
  assert.throws(() => validateSnapshot({ date: "2026-07-12", dca_risk: 0.25 }, now), /stale/);
  assert.throws(() => validateSnapshot({ date: "2026-07-16", dca_risk: 0.25 }, now), /future-dated/);
});

test("validateSnapshot rejects malformed risk and dates", () => {
  assert.throws(() => validateSnapshot({ date: "2026-07-15", dca_risk: null }, now), /finite dca_risk/);
  assert.throws(() => validateSnapshot({ date: "not-a-date", dca_risk: 0.25 }, now), /valid date/);
});
