# Build order progress

Tracks completion of phases from [BACKEND_PLAN.md](BACKEND_PLAN.md#build-order). Update this file as work advances.

| Phase | Status | Notes |
|-------|--------|--------|
| **Phase 1 — Data Foundation** | Complete | Supabase + pgvector; schema applied; documents, rdf_triples, entity_aliases migrated from SQLite; chunks table empty (Phase 2) |
| **Phase 2 — Vector Index** | Complete | chunk_documents.py populated chunks; embed_chunks.py filled embeddings (no NULL embedding rows remaining); create_indexes.py implemented to ensure pgvector ivfflat indexes on chunks.embedding and chunks.summary_embedding |
| **Phase 3 — Retrieval Layer** | Complete | Query expansion (query_expansion.expand_query), summary search (summary_search.summary_search), chunk search (chunk_search.chunk_search), triple lookup (triple_lookup.triple_lookup), and context builder (context_builder.build_context_prompt) implemented |
| **Phase 4 — LLM Integration** | Complete | context_builder returns system/user prompts; retrieval/llm_generation.py calls Claude; api/chat.run_chat_pipeline runs stages 1–6 and returns answer, sources, triples |
| **Phase 5 — API Layer** | Complete | FastAPI app in api/main.py; GET /api/chat (enriched sources), /api/document/{doc_id}, /api/document/{doc_id}/text, /api/search, /api/stats, /api/tag-clusters, **GET /api/graph**. Run: `cd backend && python -m uvicorn api.main:app --host 0.0.0.0 --port 8000` |
| **Phase 6 — Frontend Integration** | Complete | Frontend calls GET /api/chat?q= and GET /api/search?q=; sources mapped to EvidenceCard, triples shown in timeline; document modal on source card click (GET /api/document/{doc_id}/text). **Network (graph) mode:** GET /api/graph for entity-relationship graph; react-force-graph-2d; sidebar with stats, entity/keyword/date filters, and structured facts for selected node. VITE_API_URL or default http://localhost:8000. |

**Entity relationship graph:** GET /api/graph returns nodes (entities from rdf_triples actor/target) and edges (triples) with optional filters: entity, date_from, date_to, keywords, limit. Frontend "Network" tab shows force-directed graph; click node to see triples in sidebar; "View doc" opens document modal. Optional: run `backend/ingestion/index_rdf_triples_target.sql` in Supabase SQL editor to add index on rdf_triples(target) for graph queries.

**RAG retrieval (hybrid candidates):** Query expansion now tokenizes multi-word queries and looks up entity_aliases per token so terms like "Trump", "Epstein", "minors" are expanded. Triple-based candidate search (`get_doc_ids_by_triple_terms` RPC) returns doc_ids from `rdf_triples` by actor/target/action match; these are merged with summary-search candidates in the chat pipeline. **Required:** Run `backend/ingestion/rpc_triple_candidate_doc_ids.sql` in the Supabase SQL editor once so the RPC exists.

**Auth:** Sign-in is required before asking a question. Supabase Auth with **Google OAuth** is used; frontend sends a JWT on `/api/chat`. Enable the Google provider in Supabase Dashboard → Authentication → Providers and add your redirect URLs (e.g. `http://localhost:5173` for Vite dev). Backend verifies JWT (SUPABASE_JWT_SECRET) and returns 401 if missing/invalid.

**If you get 401 on `/api/chat`:** (1) In backend `.env`, set `SUPABASE_JWT_SECRET` to the exact value from **Supabase Dashboard → Project Settings → API → JWT Secret** (same project as your frontend). (2) Sign in again in the app (Google); if the token was expired or from another project, signing out and back in fixes it.

**Status values:** `Not started` | `In progress` | `Complete`

# Build order progress

Tracks completion of phases from [BACKEND_PLAN.md](BACKEND_PLAN.md#build-order). Update this file as work advances.

| Phase | Status | Notes |
|-------|--------|--------|
| **Phase 1 — Data Foundation** | Complete | Supabase + pgvector; schema applied; documents, rdf_triples, entity_aliases migrated from SQLite; chunks table empty (Phase 2) |
| **Phase 2 — Vector Index** | Complete | chunk_documents.py populated chunks; embed_chunks.py filled embeddings (no NULL embedding rows remaining); create_indexes.py implemented to ensure pgvector ivfflat indexes on chunks.embedding and chunks.summary_embedding |
| **Phase 3 — Retrieval Layer** | Complete | Query expansion (query_expansion.expand_query), summary search (summary_search.summary_search), chunk search (chunk_search.chunk_search), triple lookup (triple_lookup.triple_lookup), and context builder (context_builder.build_context_prompt) implemented |
| **Phase 4 — LLM Integration** | Complete | context_builder returns system/user prompts; retrieval/llm_generation.py calls Claude; api/chat.run_chat_pipeline runs stages 1–6 and returns answer, sources, triples |
| **Phase 5 — API Layer** | Complete | FastAPI app in api/main.py; GET /api/chat (enriched sources), /api/document/{doc_id}, /api/document/{doc_id}/text, /api/search, /api/stats, /api/tag-clusters, **GET /api/graph**. Run: `cd backend && python -m uvicorn api.main:app --host 0.0.0.0 --port 8000` |
| **Phase 6 — Frontend Integration** | Complete | Frontend calls GET /api/chat?q= and GET /api/search?q=; sources mapped to EvidenceCard, triples shown in timeline; document modal on source card click (GET /api/document/{doc_id}/text). **Network (graph) mode:** GET /api/graph for entity-relationship graph; react-force-graph-2d; sidebar with stats, entity/keyword/date filters, and structured facts for selected node. VITE_API_URL or default http://localhost:8000. |

**Entity relationship graph:** GET /api/graph returns nodes (entities from rdf_triples actor/target) and edges (triples) with optional filters: entity, date_from, date_to, keywords, limit. Frontend "Network" tab shows force-directed graph; click node to see triples in sidebar; "View doc" opens document modal. Optional: run `backend/ingestion/index_rdf_triples_target.sql` in Supabase SQL editor to add index on rdf_triples(target) for graph queries.

**RAG retrieval (hybrid candidates):** Query expansion now tokenizes multi-word queries and looks up entity_aliases per token so terms like "Trump", "Epstein", "minors" are expanded. Triple-based candidate search (`get_doc_ids_by_triple_terms` RPC) returns doc_ids from `rdf_triples` by actor/target/action match; these are merged with summary-search candidates in the chat pipeline. **Required:** Run `backend/ingestion/rpc_triple_candidate_doc_ids.sql` in the Supabase SQL editor once so the RPC exists.

**Auth and chat sessions:** Sign-in is required before asking a question. Supabase Auth with **Google OAuth** is used; frontend sends JWT on `/api/chat` and session APIs. Enable the Google provider in Supabase Dashboard → Authentication → Providers and add your redirect URLs (e.g. `http://localhost:5173` for Vite dev). Backend verifies JWT (SUPABASE_JWT_SECRET) and returns 401 if missing/invalid. Chat sessions: run `backend/ingestion/schema_chat_sessions.sql` in Supabase SQL editor to create `chat_sessions` and `chat_messages` with RLS. POST/GET/DELETE `/api/sessions`, GET `/api/sessions/{id}` for messages; GET `/api/chat?q=...&session_id=...` persists the turn when session_id is provided. Frontend: session sidebar, "New chat", load session and message history.

**If you get 401 on `/api/sessions` or `/api/chat`:** (1) In backend `.env`, set `SUPABASE_JWT_SECRET` to the exact value from **Supabase Dashboard → Project Settings → API → JWT Secret** (same project as your frontend). (2) Sign in again in the app (Google); if the token was expired or from another project, signing out and back in fixes it.

**Status values:** `Not started` | `In progress` | `Complete`
