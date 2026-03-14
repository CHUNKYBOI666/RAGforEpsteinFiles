# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RAG for EFN is a conversational research tool with semantic search over a document corpus. It combines vector embeddings, structured RDF triples, and an LLM to answer natural-language questions with source citations.

## Development Commands

### Backend
```bash
cd backend
pip3 install -r requirements.txt
cp .env.example .env        # then fill in credentials
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env        # set VITE_API_URL if not using default localhost:8000
npm run dev                  # dev server on port 3000
npm run build                # production build
npm run lint                 # TypeScript type-check (tsc --noEmit)
```

## Architecture

### Stack
- **Backend**: Python 3.10+, FastAPI, Uvicorn
- **Frontend**: React 19, Vite 6, TypeScript, Tailwind CSS v4, `react-force-graph-2d`
- **Database**: Supabase (PostgreSQL + pgvector)
- **Embeddings**: OpenAI `text-embedding-3-small` (1536-dim)
- **LLM**: Any OpenAI-compatible API (OpenRouter, Groq, Ollama, etc.)

### Database Schema
Four core tables in Supabase:
1. **`documents`** — `doc_id`, `full_text`, `paragraph_summary`, `one_sentence_summary`, `category`, `date_range_earliest/latest`
2. **`chunks`** — `doc_id`, `chunk_index`, `chunk_text`, `embedding` (vector), `summary_embedding` (vector)
3. **`rdf_triples`** — Structured facts: `actor`, `action`, `target`, `location`, `timestamp`, `doc_id`
4. **`entity_aliases`** — `original_name` → `canonical_name` mapping for query expansion

### 6-Stage RAG Pipeline (`backend/api/chat.py`)
Runs sequentially — do not skip or reorder stages:
1. **Query Expansion** (`retrieval/query_expansion.py`) — look up entity aliases in DB
2. **Summary Search** (`retrieval/summary_search.py`) — coarse vector search on `summary_embedding` → candidate `doc_id`s
3. **Chunk Search** (`retrieval/chunk_search.py`) — fine vector search on `embedding` within candidates
4. **Triple Candidate Search** (`retrieval/triple_candidate_search.py`) — RPC call for `doc_id`s matching triple terms
5. **Context Builder** (`retrieval/context_builder.py`) — assemble system/user prompts from chunks + triples
6. **LLM Generation** (`retrieval/llm_generation.py`) — call OpenAI-compatible LLM

### API Endpoints (`/api/*`)
| Endpoint | Description |
|----------|-------------|
| `GET /api/chat?q=QUERY` | RAG Q&A; returns `{ answer, sources, triples }` |
| `GET /api/document/{doc_id}` | Document metadata |
| `GET /api/document/{doc_id}/text` | Full document text |
| `GET /api/search?q=QUERY` | Entity/actor search |
| `GET /api/entities` | All entities for graph dropdown |
| `GET /api/graph` | Force-graph data (nodes + edges) with optional filters |
| `GET/POST /api/stats` | DB counts |
| `GET/POST/DELETE /api/sessions` | Device-based chat sessions |

Chat response contract (always return all fields, empty arrays if missing):
```json
{ "answer": "...", "sources": [...], "triples": [...] }
```

### Frontend (`frontend/src/`)
- **`App.tsx`** — Main component; 3 modes: chat (Synthesize), search (Raw), graph (Network)
- **`api.ts`** — All API calls; maps backend responses to UI types
- **`types.ts`** — TypeScript interfaces (`ChatResponse`, `Source`, `Triple`, `GraphNode`, etc.)
- **`components/EvidenceCard.tsx`** — Source document cards with click-to-modal
- **`components/RelationshipGraph.tsx`** — `react-force-graph-2d` visualization
- **`lib/deviceId.ts`** — Stable device UUID in localStorage (used for session auth via `X-Device-Id` header)

### Configuration (`backend/config.py`)
All config via environment variables. Required:
```
SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET
OPENAI_API_KEY
LLM_BASE_URL, LLM_MODEL, LLM_API_KEY
```
Optional tuning vars: `CHUNK_SIZE` (400), `CHUNK_OVERLAP` (50), `SUMMARY_TOP_K` (20), `MAX_CANDIDATE_DOCS` (40), `CHUNK_TOP_K` (5).

## Constraints
- Backend is Python/FastAPI only — no Node.js for the RAG API
- Database is Supabase/pgvector only — no other vector DBs (Pinecone, Chroma, etc.)
- No hardcoded credentials; use environment variables

## One-Time Data Ingestion (already completed)
If re-ingesting data:
1. Run `backend/ingestion/schema.sql` in Supabase SQL Editor
2. Run `backend/ingestion/rpc_triple_candidate_doc_ids.sql`
3. `python3 ingestion/migrate_sqlite.py` — SQLite → Supabase
4. `python3 ingestion/chunk_documents.py` — split full_text into chunks
5. `python3 ingestion/embed_chunks.py` — generate OpenAI embeddings (~$1 cost)
6. `python3 ingestion/create_indexes.py` — create IVFFlat indexes
