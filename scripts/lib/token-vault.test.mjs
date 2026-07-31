import assert from "node:assert/strict";
import test from "node:test";
import { decryptToken, encryptToken } from "./token-vault.mjs";

test("token vault persists retryable tokens without plaintext at rest", () => {
  const encrypted = encryptToken("unsubscribe-secret", "provider-secret");
  assert.doesNotMatch(encrypted.ciphertext, /unsubscribe-secret/);
  assert.equal(decryptToken(encrypted.ciphertext, encrypted.nonce, "provider-secret"), "unsubscribe-secret");
  assert.throws(() => decryptToken(encrypted.ciphertext, encrypted.nonce, "wrong-secret"));
});
