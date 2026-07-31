import assert from "node:assert/strict";
import test from "node:test";
import { deliveryIdempotencyKey, ensureAlertSchema, retentionCutoff } from "./alert-deliveries.mjs";

test("delivery idempotency is deterministic per subscriber release and zone", () => {
  const input = { subscriberId: 42, releaseId: "release-abc", zone: "buy" };
  assert.equal(deliveryIdempotencyKey(input), "risk-metric:release-abc:42:buy");
  assert.equal(deliveryIdempotencyKey(input), deliveryIdempotencyKey(input));
  assert.notEqual(deliveryIdempotencyKey(input), deliveryIdempotencyKey({ ...input, zone: "sell" }));
});

test("retentionCutoff keeps roughly one year of delivery history", () => {
  assert.equal(retentionCutoff(new Date("2026-07-16T06:00:00Z")), "2025-07-16T06:00:00.000Z");
});

test("ensureAlertSchema adds only missing migration columns", async () => {
  const statements = [];
  const query = async (_env, sql) => {
    statements.push(sql);
    if (sql === "PRAGMA table_info(subscribers)") return [{ name: "confirm_token_hash" }];
    if (sql === "PRAGMA table_info(alert_deliveries)") return [{ name: "unsubscribe_token_ciphertext" }];
    return [];
  };
  await ensureAlertSchema(query, {});
  assert(statements.some((sql) => sql.includes("ADD COLUMN unsubscribe_token_hash")));
  assert(!statements.some((sql) => sql.includes("ADD COLUMN confirm_token_hash")));
  assert(statements.some((sql) => sql.includes("ADD COLUMN unsubscribe_token_nonce")));
});
