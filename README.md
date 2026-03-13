

https://github.com/user-attachments/assets/a3f3e005-8502-4dce-aca5-b7402c0ec927


# RAG for Epstein Document Explorer

A **conversational research tool** over a document corpus: ask natural-language questions and get answers with direct citations to source documents. It combines **semantic (vector) search**, **structured relationship data** (actor–action–target triples), and an **LLM** to produce grounded, sourced responses—like talking to a researcher who has read every document and always shows their work.

**Try it here:** 

---

## What This Project Does

- **Q&A with citations** — Ask questions in plain language; answers include source documents and structured facts (triples) you can click through.
- **Entity search** — Search for people and entities; see relationship counts and canonical names.
- **Relationship graph** — Explore entities and their connections in an interactive force-directed graph with filters (entity, keywords, date range).
- **Document viewer** — Open any cited document to read the full text.

Sign-in with **Google** (Supabase Auth) is required to use the chat. The app uses the same document corpus and extraction output as the [Epstein Document Explorer](https://github.com/maxandrews/Epstein-doc-explorer); this project adds the RAG pipeline (chunking, embedding, retrieval, and LLM generation) on top of that data.

---

## Tech Stack

| Layer       | Technology |
|------------|------------|
| **Frontend** | React 19, Vite 6, TypeScript, Tailwind CSS 4, Motion, React Markdown, Supabase Auth, react-force-graph-2d |
| **Backend**  | Python 3, FastAPI, Uvicorn |
| **Database** | Supabase (PostgreSQL + pgvector) — single database for relational data and vector search |
| **Embeddings** | OpenAI `text-embedding-3-small` (1536 dims) |
| **LLM**     | Llama 3.3 70B Instruct via OpenRouter (OpenAI-compatible API). |

---

## System Design

### Data source

The corpus and extracted entities/relationships come from the [Epstein Document Explorer](https://github.com/maxandrews/Epstein-doc-explorer) project: a single SQLite file (`document_analysis.db`) containing:

- **documents** — Full text, paragraph summary, one-sentence summary, category, date ranges.
- **rdf_triples** — Structured facts: `(actor, action, target, location, timestamp, doc_id)`.
- **entity_aliases** — Name variants mapped to canonical names (e.g. "Jeff Epstein" → "Jeffrey Epstein") for query expansion.

This project **does not** re-run their extraction pipeline. It treats that database as the starting dataset: data is migrated into Supabase, then chunked and embedded to build the vector index.

### Ingestion (one-time, offline)

1. **Migration** — Copy `documents`, `rdf_triples`, and `entity_aliases` from SQLite into Supabase.
2. **Chunking** — Split each document’s `full_text` into overlapping chunks (~400 tokens, 50-token overlap).
3. **Embedding** — Generate embeddings for each chunk (OpenAI `text-embedding-3-small`) and for each document’s `paragraph_summary` (stored as `summary_embedding` on chunks).
4. **Indexes** — Create pgvector `ivfflat` indexes on `chunks.embedding` and `chunks.summary_embedding` for fast approximate nearest-neighbor search.

### Retrieval (every chat query) — 6 stages

Each `/api/chat` request runs this pipeline in order:

1. **Query expansion** — Look up the user’s query (and tokenized terms) in `entity_aliases` to include all known name variants in the search.
2. **Summary-level search** — Embed the query and search `summary_embedding` to get a small set of candidate `doc_id`s (coarse pass). Optionally merge with **triple-based** candidates (doc_ids from `rdf_triples` matching actor/target/action).
3. **Chunk-level search** — Within those candidates, search the full chunk `embedding` and return the top chunks (fine pass).
4. **Triple lookup** — For the doc_ids of those chunks, fetch relevant `rdf_triples` filtered by expanded query terms.
5. **Context assembly** — Build the LLM prompt from: retrieved chunk texts (with doc_id labels), filtered triples, and a system instruction to answer only from context and cite doc_ids.
6. **LLM generation** — Send the prompt to the configured OpenAI-compatible LLM; return **answer**, **sources**, and **triples**.

All responses include `answer` (string), `sources` (array), and `triples` (array); empty arrays when none.

### API and frontend

- **Backend** — FastAPI app: `/api/chat`, `/api/document/{doc_id}`, `/api/document/{doc_id}/text`, `/api/search`, `/api/stats`, `/api/graph`, `/api/entities`, plus session endpoints when chat sessions are enabled.
- **Frontend** — Three modes: **Synthesize** (chat + RAG), **Raw Search** (entity search), **Network** (relationship graph). Source cards and triples map to the existing EvidenceCard and timeline-style UI; document modal loads full text via `/api/document/{doc_id}/text`.

---

## How to Run It

### Prerequisites

- **Python 3.10+** (backend)
- **Node.js 18+** (frontend)
- **Supabase project** with pgvector enabled

### 1. Clone and install

```bash
git clone <this-repo>
cd RAGforEFN
```

### 2. Backend setup

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
```

Set your credentials in `backend/.env` (Supabase, OpenAI for embeddings, LLM endpoint and model).

### 3. One-time Supabase setup

In the **Supabase SQL Editor**, run (in order):

1. **Schema and tables** — `backend/ingestion/schema.sql` (creates `documents`, `rdf_triples`, `entity_aliases`, `chunks` and base indexes). Ensure the `vector` extension is enabled in your project.
2. **RPC for RAG** — `backend/ingestion/rpc_triple_candidate_doc_ids.sql` (required for hybrid candidate search in the chat pipeline).
3. **Optional** — `backend/ingestion/index_rdf_triples_target.sql` (index on `rdf_triples(target)` for graph queries).
4. **Optional (chat sessions)** — If you use session persistence, run the chat sessions schema script.

Then run the **ingestion pipeline** once (from repo root, with `document_analysis.db` available):

- Phase 1: migrate SQLite → Supabase (`migrate_sqlite.py`)
- Phase 2: chunk and embed (`chunk_documents.py`, `embed_chunks.py`), then `create_indexes.py`

### 4. Start the backend

```bash
cd backend
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### 5. Frontend setup and run

```bash
cd frontend
npm install
cp .env.example .env
```

Set Supabase and API URL in `frontend/.env`, then:

```bash
npm run dev
```

Open the app (e.g. **http://localhost:3000**). Sign in with Google, then use **Synthesize** to ask questions, **Raw Search** for entity search, or **Network** for the relationship graph.

---

## Project structure

```
RAGforEFN/
├── backend/
│   ├── api/           # FastAPI routes: main.py, chat.py, documents.py, search.py, stats.py, graph.py, entities.py, auth.py
│   ├── ingestion/     # One-time pipeline: schema.sql, migrate_sqlite.py, chunk_documents.py, embed_chunks.py, create_indexes.py, RPC/index SQLs
│   ├── retrieval/     # 6-stage RAG: query_expansion, summary_search, chunk_search, triple_lookup, triple_candidate_search, context_builder, llm_generation
│   ├── config.py      # Env-only config (Supabase, OpenAI, LLM, chunk/retrieval tuning)
│   └── requirements.txt
├── frontend/          # React + Vite + Tailwind; App.tsx (Synthesize / Raw Search / Network), api.ts, AuthContext, EvidenceCard, RelationshipGraph
└── README.md
```

---

## API overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat?q=` | GET | RAG Q&A. Returns `{ answer, sources, triples }`. Requires `Authorization: Bearer <JWT>`. |
| `/api/document/{doc_id}` | GET | Document metadata. |
| `/api/document/{doc_id}/text` | GET | Full document text. |
| `/api/search?q=` | GET | Entity/actor search; canonical names + counts. |
| `/api/stats` | GET | Counts: documents, triples, chunks, actors. |
| `/api/graph` | GET | Nodes and edges for relationship graph (optional filters: entity, date_from, date_to, keywords, limit). |
| `/api/entities` | GET | Preset list of entities (names + counts) for graph UI. |
