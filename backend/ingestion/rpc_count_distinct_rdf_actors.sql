-- RPC: distinct actor count for GET /api/stats (one round-trip; avoids scanning rdf_triples via many paginated REST calls).
-- Run once in Supabase SQL Editor (same workflow as rpc_triple_candidate_doc_ids.sql).

CREATE OR REPLACE FUNCTION public.count_distinct_rdf_actors()
RETURNS bigint
LANGUAGE sql
STABLE
AS $$
  SELECT COUNT(DISTINCT TRIM(actor))::bigint
  FROM rdf_triples
  WHERE actor IS NOT NULL AND TRIM(actor) <> '';
$$;

GRANT EXECUTE ON FUNCTION public.count_distinct_rdf_actors() TO service_role;
