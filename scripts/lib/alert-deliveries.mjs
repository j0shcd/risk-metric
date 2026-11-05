export function deliveryIdempotencyKey({ subscriberId, releaseId, zone }) {
  return `risk-metric:${releaseId}:${subscriberId}:${zone}`;
}

export function retentionCutoff(now = new Date(), retentionDays = 365) {
  return new Date(now.getTime() - retentionDays * 86_400_000).toISOString();
}

const REQUIRED_SUBSCRIBER_COLUMNS = [
  ["confirm_token_hash", "TEXT"],
  ["unsubscribe_token_hash", "TEXT"],
  ["last_confirmation_sent_at", "TEXT"],
  ["confirmation_claimed_at", "TEXT"],
  // Migration 0003. The sender selects `watch`, so a database that missed the
  // migration must gain it here rather than stop sending alerts.
  ["watch", "TEXT NOT NULL DEFAULT 'both' CHECK (watch IN ('both','high','low'))"],
  ["pending_watch", "TEXT"],
];

export async function ensureAlertSchema(query, env) {
  const subscriberColumns = await query(env, "PRAGMA table_info(subscribers)");
  const existingSubscriberColumns = new Set(subscriberColumns.map((row) => row.name));
  for (const [column, definition] of REQUIRED_SUBSCRIBER_COLUMNS) {
    if (!existingSubscriberColumns.has(column)) {
      await query(env, `ALTER TABLE subscribers ADD COLUMN ${column} ${definition}`);
    }
  }

  await query(env, `CREATE TABLE IF NOT EXISTS confirmation_send_limits (
    bucket TEXT PRIMARY KEY,
    send_count INTEGER NOT NULL DEFAULT 0 CHECK (send_count >= 0)
  )`);
  await query(env, `CREATE TABLE IF NOT EXISTS alert_deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subscriber_id INTEGER NOT NULL,
    release_id TEXT NOT NULL,
    zone TEXT NOT NULL CHECK (zone IN ('buy', 'sell')),
    status TEXT NOT NULL CHECK (status IN ('pending', 'sent', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    resend_idempotency_key TEXT NOT NULL UNIQUE,
    unsubscribe_token_ciphertext TEXT,
    unsubscribe_token_nonce TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    sent_at TEXT,
    FOREIGN KEY (subscriber_id) REFERENCES subscribers(id) ON DELETE CASCADE,
    UNIQUE (subscriber_id, release_id, zone)
  )`);
  const deliveryColumns = await query(env, "PRAGMA table_info(alert_deliveries)");
  const existingDeliveryColumns = new Set(deliveryColumns.map((row) => row.name));
  for (const column of ["unsubscribe_token_ciphertext", "unsubscribe_token_nonce"]) {
    if (!existingDeliveryColumns.has(column)) {
      await query(env, `ALTER TABLE alert_deliveries ADD COLUMN ${column} TEXT`);
    }
  }
  await query(env, "CREATE INDEX IF NOT EXISTS idx_alert_deliveries_created_at ON alert_deliveries(created_at)");
  await query(env, "CREATE UNIQUE INDEX IF NOT EXISTS idx_subscribers_confirm_token_hash ON subscribers(confirm_token_hash)");
  await query(env, "CREATE UNIQUE INDEX IF NOT EXISTS idx_subscribers_unsubscribe_token_hash ON subscribers(unsubscribe_token_hash)");
}
