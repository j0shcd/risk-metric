ALTER TABLE subscribers ADD COLUMN confirm_token_hash TEXT;
ALTER TABLE subscribers ADD COLUMN unsubscribe_token_hash TEXT;
ALTER TABLE subscribers ADD COLUMN last_confirmation_sent_at TEXT;
ALTER TABLE subscribers ADD COLUMN confirmation_claimed_at TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_subscribers_confirm_token_hash ON subscribers(confirm_token_hash);
CREATE UNIQUE INDEX IF NOT EXISTS idx_subscribers_unsubscribe_token_hash ON subscribers(unsubscribe_token_hash);

CREATE TABLE IF NOT EXISTS confirmation_send_limits (
  bucket TEXT PRIMARY KEY,
  send_count INTEGER NOT NULL DEFAULT 0 CHECK (send_count >= 0)
);

CREATE TABLE IF NOT EXISTS alert_deliveries (
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
);

CREATE INDEX IF NOT EXISTS idx_alert_deliveries_created_at ON alert_deliveries(created_at);
