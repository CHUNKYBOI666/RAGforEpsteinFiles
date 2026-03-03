-- Allow NULL in chat_messages.sources and chat_messages.triples so inserts
-- never fail if the client sends null; app coalesces to [] on read.
-- Run in Supabase SQL editor after schema_chat_sessions.sql.

ALTER TABLE public.chat_messages
  ALTER COLUMN sources DROP NOT NULL,
  ALTER COLUMN triples DROP NOT NULL;
