CREATE TABLE IF NOT EXISTS subscribers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  buy_threshold REAL NOT NULL,
  sell_threshold REAL NOT NULL,
  pending_buy_threshold REAL,
  pending_sell_threshold REAL,
  status TEXT NOT NULL DEFAULT 'pending',
  -- Legacy plaintext columns remain nullable during migration. New writes use hashes only.
  confirm_token TEXT UNIQUE,
  unsubscribe_token TEXT UNIQUE,
  confirm_token_hash TEXT UNIQUE,
  unsubscribe_token_hash TEXT UNIQUE,
  last_zone TEXT,
  last_alert_at TEXT,
  last_confirmation_sent_at TEXT,
  confirmation_claimed_at TEXT,
  created_at TEXT NOT NULL,
  confirmed_at TEXT
);

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
