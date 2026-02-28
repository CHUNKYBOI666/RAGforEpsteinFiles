# Build order progress

Tracks completion of phases from [BACKEND_PLAN.md](BACKEND_PLAN.md#build-order). Update this file as work advances.

| Phase | Status | Notes |
|-------|--------|--------|
| **Phase 1 — Data Foundation** | Complete | Supabase + pgvector; schema applied; documents, rdf_triples, entity_aliases migrated from SQLite; chunks table empty (Phase 2) |
| **Phase 2 — Vector Index** | Complete | chunk_documents.py populated chunks; embed_chunks.py filled embeddings (no NULL embedding rows remaining); create_indexes.py implemented to ensure pgvector ivfflat indexes on chunks.embedding and chunks.summary_embedding |
| **Phase 3 — Retrieval Layer** | Complete | Query expansion (query_expansion.expand_query), summary search (summary_search.summary_search), chunk search (chunk_search.chunk_search), triple lookup (triple_lookup.triple_lookup), and context builder (context_builder.build_context_prompt) implemented |
| **Phase 4 — LLM Integration** | Complete | context_builder returns system/user prompts; retrieval/llm_generation.py calls Claude; api/chat.run_chat_pipeline runs stages 1–6 and returns answer, sources, triples |
| **Phase 5 — API Layer** | Complete | FastAPI app in api/main.py; GET /api/chat (enriched sources), /api/document/{doc_id}, /api/document/{doc_id}/text, /api/search, /api/stats, /api/tag-clusters. Run: `cd backend && python -m uvicorn api.main:app --host 0.0.0.0 --port 8000` |
| **Phase 6 — Frontend Integration** | Complete | Frontend calls GET /api/chat?q= and GET /api/search?q=; sources mapped to EvidenceCard, triples shown in timeline; document modal on source card click (GET /api/document/{doc_id}/text). VITE_API_URL or default http://localhost:8000. |

**Status values:** `Not started` | `In progress` | `Complete`
