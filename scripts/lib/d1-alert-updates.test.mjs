import assert from "node:assert/strict";
import test from "node:test";
import { batchUpdateStatements, buildUpdateStatement, extractD1Results } from "./d1-alert-updates.mjs";

function update(id, alerted = true) {
  return { id, zone: "buy", alerted, alertedAt: alerted ? "2026-07-15T06:00:00Z" : undefined };
}

test("buildUpdateStatement binds only the requested subscriber updates", () => {
  const statement = buildUpdateStatement([update(1), update(2, false)]);
  assert.equal(statement.params.length, 8);
  assert.deepEqual(statement.params, [1, "buy", 2, "buy", 1, "2026-07-15T06:00:00Z", 1, 2]);
});

test("batchUpdateStatements keeps every batch below 100 D1 parameters", () => {
  const belowBoundary = batchUpdateStatements(Array.from({ length: 19 }, (_, index) => update(index + 1)));
  assert.equal(belowBoundary.length, 1);
  assert.equal(belowBoundary[0].params.length, 95);

  const atBoundary = batchUpdateStatements(Array.from({ length: 20 }, (_, index) => update(index + 1)));
  assert.deepEqual(atBoundary.map((statement) => statement.params.length), [95, 5]);
});

test("batchUpdateStatements uses available capacity for silent zone updates", () => {
  const statements = batchUpdateStatements(Array.from({ length: 34 }, (_, index) => update(index + 1, false)));
  assert.deepEqual(statements.map((statement) => statement.params.length), [99, 3]);
});

test("extractD1Results rejects a failed nested D1 result", () => {
  assert.throws(
    () => extractD1Results({ ok: true, status: 200 }, { success: true, result: [{ success: false, error: "SQLITE_ERROR" }] }),
    /D1 query failed/,
  );
  assert.throws(() => extractD1Results({ ok: true, status: 200 }, { success: true, result: [] }), /D1 query failed/);
  assert.deepEqual(
    extractD1Results({ ok: true, status: 200 }, { success: true, result: [{ success: true, results: [{ id: 1 }] }] }),
    [{ id: 1 }],
  );
});
