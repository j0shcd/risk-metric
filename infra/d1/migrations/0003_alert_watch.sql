ALTER TABLE subscribers ADD COLUMN watch TEXT NOT NULL DEFAULT 'both' CHECK (watch IN ('both','high','low'));
ALTER TABLE subscribers ADD COLUMN pending_watch TEXT;
