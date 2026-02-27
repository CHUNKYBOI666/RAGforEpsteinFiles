# Build order progress

Tracks completion of phases from [BACKEND_PLAN.md](BACKEND_PLAN.md#build-order). Update this file as work advances.

| Phase | Status | Notes |
|-------|--------|--------|
| **Phase 1 — Data Foundation** | Complete | Supabase + pgvector; schema applied; documents, rdf_triples, entity_aliases migrated from SQLite; chunks table empty (Phase 2) |
| **Phase 2 — Vector Index** | Complete | chunk_documents.py populated chunks; embed_chunks.py filled embeddings (no NULL embedding rows remaining); create_indexes.py implemented to ensure pgvector ivfflat indexes on chunks.embedding and chunks.summary_embedding |
| **Phase 3 — Retrieval Layer** | Complete | Query expansion (query_expansion.expand_query), summary search (summary_search.summary_search), chunk search (chunk_search.chunk_search), triple lookup (triple_lookup.triple_lookup), and context builder (context_builder.build_context_prompt) implemented |
| **Phase 4 — LLM Integration** | Not started | Wire context to Claude; tune system prompt for citations |
| **Phase 5 — API Layer** | Not started | FastAPI endpoints; response format for frontend |
| **Phase 6 — Frontend Integration** | Not started | Chat input; wire /api/chat to DocumentModal and timeline |

**Status values:** `Not started` | `In progress` | `Complete`
