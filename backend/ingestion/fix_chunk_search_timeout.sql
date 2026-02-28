-- Run this once in Supabase SQL Editor to fix "statement timeout" on chunk search.
-- The default Postgres statement timeout (e.g. 8s) can be exceeded by the vector RPCs
-- when searching over many chunks. This gives them 30 seconds.

ALTER FUNCTION public.match_chunks_in_docs(vector, text[], integer) SET statement_timeout = '30s';
ALTER FUNCTION public.match_chunks_summary(vector, integer) SET statement_timeout = '30s';
