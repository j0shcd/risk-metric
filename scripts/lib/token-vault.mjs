import crypto from "node:crypto";

function keyFromSecret(secret) {
  if (!secret) throw new Error("token vault secret is not configured");
  return crypto.createHash("sha256").update(`risk-metric:unsubscribe:${secret}`).digest();
}

export function encryptToken(token, secret) {
  const nonce = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv("aes-256-gcm", keyFromSecret(secret), nonce);
  const ciphertext = Buffer.concat([cipher.update(token, "utf8"), cipher.final(), cipher.getAuthTag()]);
  return { ciphertext: ciphertext.toString("base64url"), nonce: nonce.toString("base64url") };
}

export function decryptToken(ciphertext, nonce, secret) {
  const packed = Buffer.from(ciphertext, "base64url");
  const tag = packed.subarray(packed.length - 16);
  const encrypted = packed.subarray(0, packed.length - 16);
  const decipher = crypto.createDecipheriv("aes-256-gcm", keyFromSecret(secret), Buffer.from(nonce, "base64url"));
  decipher.setAuthTag(tag);
  return Buffer.concat([decipher.update(encrypted), decipher.final()]).toString("utf8");
}
