import { hashToken } from "./_lib/tokens.mjs";
import { legacyTokenCandidate } from "./_lib/token-compat.mjs";

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => {
    const entities = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
    return entities[char];
  });
}

function html(body, status = 200) {
  return new Response(`<!doctype html><html><head><meta charset="utf-8"><title>Risk alerts</title></head><body>${body}</body></html>`, {
    status,
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}

function invalid(siteUrl) {
  return html(`<h1>Link invalid or expired</h1><p>This confirmation link is invalid or expired.</p><p><a href="${escapeHtml(siteUrl)}">Back to Risk Metric</a></p>`);
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
    <h1>Confirm risk alerts</h1>
    <p>Confirm this request to activate or update your alerts.</p>
    <form method="post" action="/api/confirm">
      <input type="hidden" name="token" value="${escapeHtml(token)}">
      <button type="submit">Confirm alerts</button>
    </form>
    <p><a href="${escapeHtml(siteUrl)}">Cancel</a></p>
  `);
}

export async function onRequestPost({ request, env }) {
  const siteUrl = (env.SITE_URL || "https://risk-metric.pages.dev").replace(/\/+$/, "");
  const token = await postedToken(request);
  if (!token) return invalid(siteUrl);
  const tokenHash = await hashToken(token);
  const legacyToken = legacyTokenCandidate(env, token);

  const subscriber = await env.DB.prepare(
    `SELECT id, status, buy_threshold, sell_threshold, pending_buy_threshold, pending_sell_threshold
     FROM subscribers
     WHERE (confirm_token_hash = ? OR confirm_token = ?) AND status IN ('pending', 'active')`,
  )
    .bind(tokenHash, legacyToken)
    .first();

  if (!subscriber) return invalid(siteUrl);

  const hasPending = subscriber.pending_buy_threshold !== null && subscriber.pending_sell_threshold !== null;
  const buyThreshold = hasPending ? subscriber.pending_buy_threshold : subscriber.buy_threshold;
  const sellThreshold = hasPending ? subscriber.pending_sell_threshold : subscriber.sell_threshold;
  const confirmedAt = new Date().toISOString();

  if (hasPending) {
    const result = await env.DB.prepare(
      `UPDATE subscribers
       SET buy_threshold = ?, sell_threshold = ?, pending_buy_threshold = NULL, pending_sell_threshold = NULL,
           last_zone = NULL, status = 'active', confirmed_at = COALESCE(confirmed_at, ?),
           confirm_token = NULL, confirm_token_hash = NULL
       WHERE id = ? AND (confirm_token_hash = ? OR (confirm_token_hash IS NULL AND confirm_token = ?))`,
    )
      .bind(buyThreshold, sellThreshold, confirmedAt, subscriber.id, tokenHash, legacyToken)
      .run();
    if ((result.meta?.changes ?? 0) === 0) return invalid(siteUrl);
  } else {
    const result = await env.DB.prepare(
      `UPDATE subscribers
       SET status = 'active', confirmed_at = ?, confirm_token = NULL, confirm_token_hash = NULL
       WHERE id = ? AND (confirm_token_hash = ? OR (confirm_token_hash IS NULL AND confirm_token = ?))`,
    )
      .bind(confirmedAt, subscriber.id, tokenHash, legacyToken)
      .run();
    if ((result.meta?.changes ?? 0) === 0) return invalid(siteUrl);
  }

  const heading = subscriber.status === "active" && hasPending ? "Thresholds updated" : "You're subscribed";
  return html(
    `<h1>${heading}</h1><p>You'll get an email when risk crosses ${escapeHtml(buyThreshold)} / ${escapeHtml(sellThreshold)}.</p><p><a href="${escapeHtml(siteUrl)}">Back to Risk Metric</a></p>`,
  );
}
