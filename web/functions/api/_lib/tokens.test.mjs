import assert from "node:assert/strict";
import test from "node:test";
import { generateToken, hashToken } from "./tokens.mjs";

test("tokens are high entropy and stored as deterministic one-way hashes", async () => {
  const first = generateToken();
  const second = generateToken();
  assert.match(first, /^[A-Za-z0-9_-]{43}$/);
  assert.notEqual(first, second);
  assert.equal(await hashToken(first), await hashToken(first));
  assert.notEqual(await hashToken(first), first);
  assert.notEqual(await hashToken(first), await hashToken(second));
});
