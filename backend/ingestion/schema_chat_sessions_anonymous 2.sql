-- Anonymous sessions: add device_id to chat_sessions for X-Device-Id–based ownership.
-- Run once in Supabase SQL Editor after schema_chat_sessions.sql.
-- Backend uses service role; anonymous rows have user_id = sentinel UUID and device_id set.

ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS device_id TEXT;
CREATE INDEX IF NOT EXISTS idx_chat_sessions_device_id ON chat_sessions (device_id);
