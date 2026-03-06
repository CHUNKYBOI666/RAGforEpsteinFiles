-- Anonymous chat sessions and messages for device-id based persistence.
-- Run once in Supabase SQL Editor. No auth.uid() — uses device_id string.
-- Backend uses service role key (bypasses RLS); ownership checked in app code.

CREATE TABLE IF NOT EXISTS chat_sessions_anonymous (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id TEXT NOT NULL,
  title TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_anon_device_id ON chat_sessions_anonymous (device_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_anon_updated_at ON chat_sessions_anonymous (updated_at DESC);

CREATE TABLE IF NOT EXISTS chat_messages_anonymous (
  id BIGSERIAL PRIMARY KEY,
  session_id UUID NOT NULL REFERENCES chat_sessions_anonymous(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content TEXT,
  sources JSONB,
  triples JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_anon_session_id ON chat_messages_anonymous (session_id);
