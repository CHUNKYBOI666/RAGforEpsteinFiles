# Build order progress

Tracks completion of phases from [BACKEND_PLAN.md](BACKEND_PLAN.md#build-order). Update this file as work advances.

| Phase | Status | Notes |
|-------|--------|--------|
| **Phase 1 — Data Foundation** | Complete | Supabase + pgvector; schema applied; documents, rdf_triples, entity_aliases migrated from SQLite; chunks table empty (Phase 2) |
| **Phase 2 — Vector Index** | Not started | Chunking + embedding scripts; populate chunks table; create ivfflat indexes |
| **Phase 3 — Retrieval Layer** | Not started | Query expansion, summary search, chunk search, triple lookup, context builder |
| **Phase 4 — LLM Integration** | Not started | Wire context to Claude; tune system prompt for citations |
| **Phase 5 — API Layer** | Not started | FastAPI endpoints; response format for frontend |
| **Phase 6 — Frontend Integration** | Not started | Chat input; wire /api/chat to DocumentModal and timeline |

**Status values:** `Not started` | `In progress` | `Complete`
