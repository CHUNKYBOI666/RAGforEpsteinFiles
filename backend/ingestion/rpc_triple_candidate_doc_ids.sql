-- RPC: return distinct doc_ids from rdf_triples where actor, target, or action
-- matches any term (ILIKE %term%). Used for triple-based candidate expansion in chat.
-- Run this in Supabase SQL editor (or migrate) after schema is applied.

CREATE OR REPLACE FUNCTION get_doc_ids_by_triple_terms(
  search_terms text[],
  max_doc_ids int DEFAULT 25
)
RETURNS TABLE (doc_id text)
LANGUAGE sql
STABLE
AS $$
  WITH limited AS (
    SELECT t.doc_id
    FROM rdf_triples t
    WHERE EXISTS (
      SELECT 1 FROM unnest(search_terms) AS term
      WHERE t.actor ILIKE '%' || term || '%'
         OR t.target ILIKE '%' || term || '%'
         OR t.action ILIKE '%' || term || '%'
    )
    LIMIT 1000
  )
  SELECT DISTINCT l.doc_id
  FROM limited l
  LIMIT max_doc_ids;
$$;
