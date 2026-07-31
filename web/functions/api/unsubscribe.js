import { hashToken } from "./_lib/tokens.mjs";
import { legacyTokenCandidate } from "./_lib/token-compat.mjs";

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => {
    const entities = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
    return entities[char];
  });
}

function html(body) {
  return new Response(`<!doctype html><html><head><meta charset="utf-8"><title>Risk alerts</title></head><body>${body}</body></html>`, {
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}

function invalid(siteUrl) {
  return html(`<h1>Unsubscribe link invalid</h1><p>This unsubscribe link is invalid or expired.</p><p><a href="${escapeHtml(siteUrl)}">Back to Risk Metric</a></p>`);
}

async function postedToken(request) {
  const contentType = request.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return (await request.json().catch(() => null))?.token ?? null;
  return (await request.formData().catch(() => null))?.get("token") ?? null;
}

export async function onRequestGet({ request, env }) {
  const siteUrl = (env.SITE_URL || "https://risk-metric.pages.dev").replace(/\/+$/, "");
  const token = new URL(request.url).searchParams.get("token");
  if (!token) return invalid(siteUrl);
  return html(`
    <h1>Unsubscribe from risk alerts?</h1>
    <form method="post" action="/api/unsubscribe">
      <input type="hidden" name="token" value="${escapeHtml(token)}">
      <button type="submit">Unsubscribe</button>
    </form>
    <p><a href="${escapeHtml(siteUrl)}">Keep alerts</a></p>
  `);
}

export async function onRequestPost({ request, env }) {
  const siteUrl = (env.SITE_URL || "https://risk-metric.pages.dev").replace(/\/+$/, "");
  const token = await postedToken(request);
  if (!token) return invalid(siteUrl);
  const tokenHash = await hashToken(token);
  const legacyToken = legacyTokenCandidate(env, token);
  const result = await env.DB.prepare(
    `UPDATE subscribers
     SET status = 'unsubscribed', unsubscribe_token = NULL, unsubscribe_token_hash = NULL,
         confirm_token = NULL, confirm_token_hash = NULL
     WHERE unsubscribe_token_hash = ? OR (unsubscribe_token_hash IS NULL AND unsubscribe_token = ?)`,
  )
    .bind(tokenHash, legacyToken)
    .run();

  if (!result.meta || result.meta.changes === 0) return invalid(siteUrl);
  return html(`<h1>You're unsubscribed</h1><p>You will no longer receive risk alerts.</p><p><a href="${escapeHtml(siteUrl)}">Back to Risk Metric</a></p>`);
}
