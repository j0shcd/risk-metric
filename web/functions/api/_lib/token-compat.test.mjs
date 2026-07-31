import assert from "node:assert/strict";
import test from "node:test";
import { legacyTokenCandidate } from "./token-compat.mjs";

test("plaintext token compatibility is explicit and time bounded", () => {
  assert.equal(legacyTokenCandidate({}, "legacy", new Date("2026-08-01T00:00:00Z")), "");
  assert.equal(
    legacyTokenCandidate({ ALLOW_LEGACY_PLAINTEXT_TOKENS: "true" }, "legacy", new Date("2026-08-01T00:00:00Z")),
    "legacy",
  );
  assert.equal(
    legacyTokenCandidate({ ALLOW_LEGACY_PLAINTEXT_TOKENS: "true" }, "legacy", new Date("2026-10-01T00:00:00Z")),
    "",
  );
});
