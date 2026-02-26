-- Supabase schema for RAG backend (Phase 1 — Data Foundation)
-- Requires: pgvector extension already enabled (create extension vector with schema extensions).
-- Tables: documents, rdf_triples, entity_aliases, chunks. No CREATE EXTENSION here.

-- 1. documents (source of truth for document metadata and text; migrated from SQLite)
CREATE TABLE documents (
  doc_id TEXT PRIMARY KEY,
  full_text TEXT,
  paragraph_summary TEXT,
  one_sentence_summary TEXT,
  category TEXT,
  date_range_earliest TEXT,
  date_range_latest TEXT
);

-- 2. rdf_triples (structured facts per document; FK to documents)
CREATE TABLE rdf_triples (
  id BIGINT PRIMARY KEY,
  doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
  actor TEXT,
  action TEXT,
  target TEXT,
  location TEXT,
  timestamp TEXT,
  top_cluster_ids TEXT
);

-- 3. entity_aliases (original_name -> canonical_name for query expansion)
CREATE TABLE entity_aliases (
  original_name TEXT NOT NULL,
  canonical_name TEXT NOT NULL,
  PRIMARY KEY (original_name, canonical_name)
);

-- 4. chunks (document chunks with embeddings; FK to documents)
CREATE TABLE chunks (
  id BIGSERIAL PRIMARY KEY,
  doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
  chunk_index INTEGER NOT NULL,
  chunk_text TEXT NOT NULL,
  embedding extensions.vector(1536),
  summary_embedding extensions.vector(1536)
);

-- B-tree indexes on rdf_triples for fast lookup (actor, doc_id, timestamp)
CREATE INDEX idx_rdf_triples_actor ON rdf_triples (actor);
CREATE INDEX idx_rdf_triples_doc_id ON rdf_triples (doc_id);
CREATE INDEX idx_rdf_triples_timestamp ON rdf_triples (timestamp);

-- IVFFlat indexes on chunks for approximate nearest-neighbor search (cosine distance)
-- Tune lists after bulk load if needed (e.g. in create_indexes.py).
CREATE INDEX idx_chunks_embedding ON chunks
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_chunks_summary_embedding ON chunks
  USING ivfflat (summary_embedding vector_cosine_ops) WITH (lists = 100);
