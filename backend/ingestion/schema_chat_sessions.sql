-- Chat sessions and messages for authenticated users. Run in Supabase SQL editor.
-- Requires Supabase Auth (auth.users). RLS ensures users only see their own data.

-- Sessions: one per conversation thread
CREATE TABLE IF NOT EXISTS public.chat_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  title text NOT NULL DEFAULT 'New chat',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON public.chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated_at ON public.chat_sessions(user_id, updated_at DESC);

-- Messages: one row per user message and one per assistant reply
CREATE TABLE IF NOT EXISTS public.chat_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL REFERENCES public.chat_sessions(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('user', 'assistant')),
  content text NOT NULL DEFAULT '',
  sources jsonb NOT NULL DEFAULT '[]',
  triples jsonb NOT NULL DEFAULT '[]',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON public.chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON public.chat_messages(session_id, created_at);

-- RLS
ALTER TABLE public.chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;

-- chat_sessions: user can only access their own
DROP POLICY IF EXISTS "chat_sessions_select_own" ON public.chat_sessions;
CREATE POLICY "chat_sessions_select_own" ON public.chat_sessions
  FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "chat_sessions_insert_own" ON public.chat_sessions;
CREATE POLICY "chat_sessions_insert_own" ON public.chat_sessions
  FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "chat_sessions_update_own" ON public.chat_sessions;
CREATE POLICY "chat_sessions_update_own" ON public.chat_sessions
  FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "chat_sessions_delete_own" ON public.chat_sessions;
CREATE POLICY "chat_sessions_delete_own" ON public.chat_sessions
  FOR DELETE USING (auth.uid() = user_id);

-- chat_messages: user can only access messages in their sessions
DROP POLICY IF EXISTS "chat_messages_select_own" ON public.chat_messages;
CREATE POLICY "chat_messages_select_own" ON public.chat_messages
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM public.chat_sessions s WHERE s.id = session_id AND s.user_id = auth.uid())
  );
DROP POLICY IF EXISTS "chat_messages_insert_own" ON public.chat_messages;
CREATE POLICY "chat_messages_insert_own" ON public.chat_messages
  FOR INSERT WITH CHECK (
    EXISTS (SELECT 1 FROM public.chat_sessions s WHERE s.id = session_id AND s.user_id = auth.uid())
  );
DROP POLICY IF EXISTS "chat_messages_delete_own" ON public.chat_messages;
CREATE POLICY "chat_messages_delete_own" ON public.chat_messages
  FOR DELETE USING (
    EXISTS (SELECT 1 FROM public.chat_sessions s WHERE s.id = session_id AND s.user_id = auth.uid())
  );
