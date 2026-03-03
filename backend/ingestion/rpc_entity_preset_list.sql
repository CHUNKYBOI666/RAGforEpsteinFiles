-- RPC: return preset list of all entities (actor + target) with relationship counts.
-- Used for instant client-side filtering in the graph entity dropdown.
-- Run in Supabase SQL editor once.

CREATE OR REPLACE FUNCTION get_entity_preset_list(max_entities int DEFAULT 2000)
RETURNS TABLE (canonical_name text, count bigint)
LANGUAGE sql
STABLE
AS $$
  WITH actor_counts AS (
    SELECT actor AS name, COUNT(*)::bigint AS c
    FROM rdf_triples
    WHERE actor IS NOT NULL AND TRIM(actor) != ''
    GROUP BY actor
  ),
  target_counts AS (
    SELECT target AS name, COUNT(*)::bigint AS c
    FROM rdf_triples
    WHERE target IS NOT NULL AND TRIM(target) != ''
    GROUP BY target
  ),
  combined AS (
    SELECT name, c FROM actor_counts
    UNION ALL
    SELECT name, c FROM target_counts
  ),
  merged AS (
    SELECT name, SUM(c) AS count
    FROM combined
    GROUP BY name
  )
  SELECT name AS canonical_name, count
  FROM merged
  ORDER BY count DESC
  LIMIT max_entities;
$$;
