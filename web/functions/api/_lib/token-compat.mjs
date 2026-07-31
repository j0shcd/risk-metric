export const LEGACY_TOKEN_DEADLINE = "2026-10-01T00:00:00Z";

export function legacyTokenCandidate(env, token, now = new Date()) {
  if (env.ALLOW_LEGACY_PLAINTEXT_TOKENS !== "true") return "";
  if (now.getTime() >= Date.parse(LEGACY_TOKEN_DEADLINE)) return "";
  return token;
}
