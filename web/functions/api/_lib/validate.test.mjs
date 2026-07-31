import assert from "node:assert/strict";
import test from "node:test";
import { isValidEmail, normalizeEmail, validateThresholds } from "./validate.mjs";

test("email validation normalizes and rejects malformed addresses", () => {
  assert.equal(normalizeEmail(" USER@Example.COM "), "user@example.com");
  assert.equal(isValidEmail(" USER@Example.COM "), true);
  assert.equal(isValidEmail("missing-at.example.com"), false);
  assert.equal(isValidEmail("a@b"), false);
  assert.equal(isValidEmail(""), false);
});

test("threshold validation accepts boundaries and ordering", () => {
  assert.deepEqual(validateThresholds(0, 1), { ok: true, buyThreshold: 0, sellThreshold: 1 });
  assert.deepEqual(validateThresholds("0.25", "0.75"), {
    ok: true,
    buyThreshold: 0.25,
    sellThreshold: 0.75,
  });
});

test("threshold validation rejects equal, out-of-range, and non-numeric values", () => {
  assert.equal(validateThresholds(0.5, 0.5).ok, false);
  assert.equal(validateThresholds(-0.1, 0.5).ok, false);
  assert.equal(validateThresholds(0.5, 1.1).ok, false);
  assert.equal(validateThresholds("abc", 0.75).ok, false);
  assert.equal(validateThresholds(0.25, Number.POSITIVE_INFINITY).ok, false);
});
