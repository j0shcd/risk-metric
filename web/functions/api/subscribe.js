import { sendEmail } from "./_lib/resend.mjs";
import { generateToken, hashToken } from "./_lib/tokens.mjs";
import { validateSubscribeInput } from "./_lib/validate.mjs";

const defaultFrom = "Risk Metric <onboarding@resend.dev>";
const genericSuccess = { ok: true, message: "Check your inbox to confirm your subscription." };
const confirmationCooldownMs = 15 * 60 * 1000;
const globalConfirmationCeiling = 50;

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => {
    const entities = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
    return entities[char];
  });
}

function confirmationEmailHtml({ siteUrl, token, buyThreshold, sellThreshold, isUpdate }) {
  const confirmUrl = `${siteUrl}/api/confirm?token=${encodeURIComponent(token)}`;
  const intro = isUpdate
    ? "<p>Confirm the new thresholds for your Bitcoin risk alerts.</p>"
    : "<p>Confirm your Bitcoin risk alerts.</p>";
  const action = isUpdate ? "Confirm your new thresholds" : "Confirm your subscription";
  const ignore = isUpdate
    ? "<p>If you did not request this change, ignore this email and your alerts stay unchanged.</p>"
    : "<p>If you did not sign up, you can ignore this email.</p>";
  return `
    ${intro}
    <p>You asked to receive alerts when dca_risk is at or below ${escapeHtml(buyThreshold)} and at or above ${escapeHtml(sellThreshold)}.</p>
    <p><a href="${escapeHtml(confirmUrl)}">${action}</a></p>
    ${ignore}
  `;
}

async function readJson(request) {
  try {
    return await request.json();
  } catch {
    return null;
  }
}

async function claimLimitSlot(db, bucket, ceiling) {
  await db.prepare("INSERT OR IGNORE INTO confirmation_send_limits (bucket, send_count) VALUES (?, 0)")
    .bind(bucket)
    .run();
  const result = await db.prepare(
    "UPDATE confirmation_send_limits SET send_count = send_count + 1 WHERE bucket = ? AND send_count < ?",
  )
    .bind(bucket, ceiling)
    .run();
  return (result.meta?.changes ?? 0) > 0;
}

async function claimConfirmationSendSlots(db, now, email) {
  const hour = now.toISOString().slice(0, 13);
  const domain = email.split("@").at(-1);
  const domainHash = await hashToken(domain);
  if (!(await claimLimitSlot(db, `${hour}:domain:${domainHash}`, 5))) return false;
  return claimLimitSlot(db, `${hour}:global`, globalConfirmationCeiling);
}

async function sendConfirmation(options) {
  try {
    await sendEmail(options);
    return true;
  } catch (error) {
    console.error(`confirmation email failed: ${error.message}`);
    return false;
  }
}

export async function onRequestPost({ request, env }) {
  const input = await readJson(request);
  const validated = validateSubscribeInput(input);

  if (!validated.ok) {
    return json({ ok: false, error: validated.error }, 400);
  }

  if (validated.website.trim() !== "") {
    return json(genericSuccess);
  }

  const nowDate = new Date();
  const now = nowDate.toISOString();
  const confirmToken = generateToken();
  const confirmTokenHash = await hashToken(confirmToken);
  const unsubscribeToken = generateToken();
  const unsubscribeTokenHash = await hashToken(unsubscribeToken);
  const siteUrl = (env.SITE_URL || "https://risk-metric.pages.dev").replace(/\/+$/, "");
  const from = env.ALERT_FROM_EMAIL || defaultFrom;

  let existing = await env.DB.prepare(
    "SELECT id, status, last_confirmation_sent_at FROM subscribers WHERE email = ?",
  )
    .bind(validated.email)
    .first();

  const claimCutoff = new Date(nowDate.getTime() - confirmationCooldownMs).toISOString();
  let isNew = false;
  if (existing) {
    const claim = await env.DB.prepare(
      `UPDATE subscribers SET confirmation_claimed_at = ?
       WHERE id = ?
         AND (last_confirmation_sent_at IS NULL OR last_confirmation_sent_at <= ?)
         AND (confirmation_claimed_at IS NULL OR confirmation_claimed_at <= ?)`,
    )
      .bind(now, existing.id, claimCutoff, claimCutoff)
      .run();
    if ((claim.meta?.changes ?? 0) === 0) return json(genericSuccess);
  } else {
    const inserted = await env.DB.prepare(
      `INSERT OR IGNORE INTO subscribers
        (email, buy_threshold, sell_threshold, status, confirm_token_hash, unsubscribe_token_hash,
         confirmation_claimed_at, created_at)
       VALUES (?, ?, ?, 'pending', ?, ?, ?, ?)`,
    )
      .bind(
        validated.email,
        validated.buyThreshold,
        validated.sellThreshold,
        confirmTokenHash,
        unsubscribeTokenHash,
        now,
        now,
      )
      .run();
    if ((inserted.meta?.changes ?? 0) === 0) return json(genericSuccess);
    isNew = true;
  }
  if (!(await claimConfirmationSendSlots(env.DB, nowDate, validated.email))) {
    return json(genericSuccess);
  }

  let sent = false;
  if (isNew) {
    sent = await sendConfirmation({
      to: validated.email,
      subject: "Confirm your risk alerts",
      html: confirmationEmailHtml({ siteUrl, token: confirmToken, ...validated }),
      from,
      apiKey: env.RESEND_API_KEY,
    });
  } else if (existing.status === "active") {
    // Never apply changes to an active subscription directly: anyone who knows
    // the email could otherwise tamper with the thresholds. Stage them and
    // require the same email confirmation as a new signup.
    await env.DB.prepare(
      `UPDATE subscribers
       SET pending_buy_threshold = ?, pending_sell_threshold = ?, confirm_token_hash = ?, confirm_token = NULL
       WHERE id = ?`,
    )
      .bind(validated.buyThreshold, validated.sellThreshold, confirmTokenHash, existing.id)
      .run();

    sent = await sendConfirmation({
      to: validated.email,
      subject: "Confirm your new risk alert thresholds",
      html: confirmationEmailHtml({ siteUrl, token: confirmToken, ...validated, isUpdate: true }),
      from,
      apiKey: env.RESEND_API_KEY,
    });
  } else {
    await env.DB.prepare(
      `UPDATE subscribers
       SET buy_threshold = ?, sell_threshold = ?, pending_buy_threshold = NULL, pending_sell_threshold = NULL,
           status = 'pending', confirm_token = NULL,
           confirm_token_hash = ?, unsubscribe_token = NULL, unsubscribe_token_hash = ?,
           last_zone = NULL, confirmed_at = NULL
       WHERE id = ?`,
    )
      .bind(validated.buyThreshold, validated.sellThreshold, confirmTokenHash, unsubscribeTokenHash, existing.id)
      .run();

    sent = await sendConfirmation({
      to: validated.email,
      subject: "Confirm your risk alerts",
      html: confirmationEmailHtml({ siteUrl, token: confirmToken, ...validated }),
      from,
      apiKey: env.RESEND_API_KEY,
    });
  }

  await env.DB.prepare(
    sent
      ? "UPDATE subscribers SET last_confirmation_sent_at = ?, confirmation_claimed_at = NULL WHERE email = ? AND confirmation_claimed_at = ?"
      : "UPDATE subscribers SET confirmation_claimed_at = NULL WHERE email = ? AND confirmation_claimed_at = ?",
  )
    .bind(...(sent ? [now, validated.email, now] : [validated.email, now]))
    .run();

  return json(genericSuccess);
}
