-- Chat sessions and messages for persistent RAG conversations.
-- Run once in Supabase SQL Editor. Requires auth.uid() (Supabase Auth).

-- chat_sessions: one per conversation, owned by user
CREATE TABLE IF NOT EXISTS chat_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  title TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated_at ON chat_sessions (updated_at DESC);

-- chat_messages: each turn (user question + assistant answer/sources/triples)
CREATE TABLE IF NOT EXISTS chat_messages (
  id BIGSERIAL PRIMARY KEY,
  session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content TEXT,
  sources JSONB,
  triples JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages (session_id);

-- RLS: users can only access their own sessions and messages
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS chat_sessions_select_own ON chat_sessions;
CREATE POLICY chat_sessions_select_own ON chat_sessions FOR SELECT USING (user_id = auth.uid());

DROP POLICY IF EXISTS chat_sessions_insert_own ON chat_sessions;
CREATE POLICY chat_sessions_insert_own ON chat_sessions FOR INSERT WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS chat_sessions_update_own ON chat_sessions;
CREATE POLICY chat_sessions_update_own ON chat_sessions FOR UPDATE USING (user_id = auth.uid());

DROP POLICY IF EXISTS chat_sessions_delete_own ON chat_sessions;
CREATE POLICY chat_sessions_delete_own ON chat_sessions FOR DELETE USING (user_id = auth.uid());

DROP POLICY IF EXISTS chat_messages_select_own ON chat_messages;
CREATE POLICY chat_messages_select_own ON chat_messages FOR SELECT
  USING (session_id IN (SELECT id FROM chat_sessions WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS chat_messages_insert_own ON chat_messages;
CREATE POLICY chat_messages_insert_own ON chat_messages FOR INSERT
  WITH CHECK (session_id IN (SELECT id FROM chat_sessions WHERE user_id = auth.uid()));
