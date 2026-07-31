#!/usr/bin/env node
import { deliveryIdempotencyKey, ensureAlertSchema, retentionCutoff } from "./lib/alert-deliveries.mjs";
import { dispatchAlerts } from "./lib/alerts-core.mjs";
import { validateSnapshot } from "./lib/alert-snapshot.mjs";
import { batchUpdateStatements, extractD1Results } from "./lib/d1-alert-updates.mjs";
import { loadValidatedAlertRelease } from "./lib/release-integrity.mjs";
import { generateToken, hashToken } from "../web/functions/api/_lib/tokens.mjs";
import { decryptToken, encryptToken } from "./lib/token-vault.mjs";

const requiredSecrets = [
  "CLOUDFLARE_API_TOKEN",
  "CLOUDFLARE_ACCOUNT_ID",
  "D1_DATABASE_ID",
  "RESEND_API_KEY",
];
const defaultSiteUrl = "https://risk-metric.pages.dev";
const defaultFrom = "Risk Metric <onboarding@resend.dev>";

function hasSecrets(env) {
  return requiredSecrets.every((key) => env[key]);
}

async function d1Query(env, sql, params = []) {
  const response = await fetch(
    `https://api.cloudflare.com/client/v4/accounts/${env.CLOUDFLARE_ACCOUNT_ID}/d1/database/${env.D1_DATABASE_ID}/query`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.CLOUDFLARE_API_TOKEN}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ sql, params }),
    },
  );

  const body = await response.json().catch(() => ({}));
  return extractD1Results(response, body);
}

async function sendEmail(env, { to, subject, html, idempotencyKey }) {
  const response = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.RESEND_API_KEY}`,
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey,
    },
    body: JSON.stringify({
      from: env.ALERT_FROM_EMAIL || defaultFrom,
      to,
      subject,
      html,
    }),
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`Resend email failed: ${response.status} ${body}`.trim());
  }
}

function readSnapshot() {
  const { manifest, snapshot } = loadValidatedAlertRelease("data/web/v2");
  return { ...validateSnapshot(snapshot), releaseId: manifest.release_id };
}

async function prepareDelivery(env, { subscriber, zone, releaseId, now }) {
  const tokenVaultSecret = env.ALERT_TOKEN_ENCRYPTION_KEY || env.RESEND_API_KEY;
  const idempotencyKey = deliveryIdempotencyKey({ subscriberId: subscriber.id, releaseId, zone });
  await d1Query(
    env,
    `INSERT OR IGNORE INTO alert_deliveries
       (subscriber_id, release_id, zone, status, attempts, resend_idempotency_key, created_at, updated_at)
     VALUES (?, ?, ?, 'pending', 0, ?, ?, ?)`,
    [subscriber.id, releaseId, zone, idempotencyKey, now, now],
  );
  const rows = await d1Query(
    env,
    `SELECT id, status, sent_at, resend_idempotency_key,
            unsubscribe_token_ciphertext, unsubscribe_token_nonce
     FROM alert_deliveries WHERE subscriber_id = ? AND release_id = ? AND zone = ?`,
    [subscriber.id, releaseId, zone],
  );
  const delivery = rows[0];
  if (!delivery) throw new Error("alert delivery reservation was not persisted");
  if (delivery.status === "sent") return { skip: true, sentAt: delivery.sent_at };

  await d1Query(
    env,
    "UPDATE alert_deliveries SET status = 'pending', attempts = attempts + 1, updated_at = ?, last_error = NULL WHERE id = ?",
    [now, delivery.id],
  );
  let unsubscribeToken;
  if (delivery.unsubscribe_token_ciphertext && delivery.unsubscribe_token_nonce) {
    unsubscribeToken = decryptToken(
      delivery.unsubscribe_token_ciphertext,
      delivery.unsubscribe_token_nonce,
      tokenVaultSecret,
    );
  } else {
    unsubscribeToken = generateToken();
    const unsubscribeTokenHash = await hashToken(unsubscribeToken);
    const encrypted = encryptToken(unsubscribeToken, tokenVaultSecret);
    await d1Query(
      env,
      `UPDATE alert_deliveries
       SET unsubscribe_token_ciphertext = ?, unsubscribe_token_nonce = ?, updated_at = ?
       WHERE id = ? AND unsubscribe_token_ciphertext IS NULL`,
      [encrypted.ciphertext, encrypted.nonce, now, delivery.id],
    );
    await d1Query(
      env,
      "UPDATE subscribers SET unsubscribe_token = NULL, unsubscribe_token_hash = ? WHERE id = ?",
      [unsubscribeTokenHash, subscriber.id],
    );
  }
  return {
    deliveryId: delivery.id,
    idempotencyKey: delivery.resend_idempotency_key,
    subscriber: { ...subscriber, unsubscribe_token: unsubscribeToken },
  };
}

async function deliverEmail(env, email) {
  try {
    await sendEmail(env, email);
    const sentAt = new Date().toISOString();
    await d1Query(
      env,
      "UPDATE alert_deliveries SET status = 'sent', sent_at = ?, updated_at = ?, last_error = NULL WHERE id = ?",
      [sentAt, sentAt, email.deliveryId],
    );
    return { sent: true };
  } catch (error) {
    const failedAt = new Date().toISOString();
    await d1Query(
      env,
      "UPDATE alert_deliveries SET status = 'failed', updated_at = ?, last_error = ? WHERE id = ?",
      [failedAt, String(error.message).slice(0, 500), email.deliveryId],
    ).catch(() => {});
    throw error;
  }
}

async function main() {
  if (!hasSecrets(process.env)) {
    console.log("alerts: secrets not configured, skipping");
    return;
  }

  const { risk, date, releaseId } = readSnapshot();
  await ensureAlertSchema(d1Query, process.env);
  await d1Query(process.env, "DELETE FROM alert_deliveries WHERE created_at < ?", [retentionCutoff()]);
  const subscribers = await d1Query(
    process.env,
    `SELECT id, email, buy_threshold, sell_threshold, last_zone
     FROM subscribers
     WHERE status = 'active'`,
  );

  const siteUrl = process.env.SITE_URL || defaultSiteUrl;
  const { updates, failures, zoneChanges, emailsSent } = await dispatchAlerts({
    risk,
    date,
    subscribers,
    siteUrl,
    prepare: ({ subscriber, zone }) => prepareDelivery(process.env, {
      subscriber,
      zone,
      releaseId,
      now: new Date().toISOString(),
    }),
    send: (email) => deliverEmail(process.env, email),
    now: () => new Date().toISOString(),
  });

  for (const failure of failures) {
    console.error(`alerts: failed sending to subscriber ${failure.id}: ${failure.error.message}`);
  }

  if (updates.length > 0) {
    for (const statement of batchUpdateStatements(updates)) {
      await d1Query(process.env, statement.sql, statement.params);
    }
  }

  console.log(
    `alerts: ${subscribers.length} active subscribers, ${zoneChanges} zone changes, ${emailsSent} emails sent`,
  );

  if (failures.length > 0) {
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(`alerts: ${error.message}`);
  process.exitCode = 1;
});
