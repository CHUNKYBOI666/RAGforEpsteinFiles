-- Optional: run in Supabase SQL Editor to speed up graph queries that filter by target.
-- GET /api/graph?entity=... uses both actor and target; this index helps the target.eq filter.

CREATE INDEX IF NOT EXISTS idx_rdf_triples_target ON rdf_triples (target);
