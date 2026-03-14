

https://github.com/user-attachments/assets/a3f3e005-8502-4dce-aca5-b7402c0ec927


# RAG for Epstein Document Explorer

Ask questions on the Epstein Files and get answers with direct citations to source documents.

[try here](rag-for-epstein-files.vercel.app)

---

## What This Project Does

- **Q&A with citations** — Ask questions in plain language; answers include source documents and structured facts you can click through.
- **Entity search** — Search for people and entities; see relationship counts and canonical names.
- **Relationship graph** — Explore entities and their connections in an interactive force-directed graph with filters (entity, keywords, date range).
- **Document viewer** — Open any cited document to read the full text.

The app uses the same document corpus and extraction output as the [Epstein Document Explorer](https://github.com/maxandrews/Epstein-doc-explorer); this project adds the RAG pipeline (chunking, embedding, retrieval, and LLM generation) on top of that data.

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

A single SQLite file (`document_analysis.db`) containing:

- **documents** — Full text, paragraph summary, one-sentence summary, category, date ranges.
- **rdf_triples** — Structured facts: `(actor, action, target, location, timestamp, doc_id)`.
- **entity_aliases** — Name variants mapped to canonical names (e.g. "Jeff Epstein" → "Jeffrey Epstein") for query expansion.

**Does not** re-run their extraction pipeline. It treats that database as the starting dataset: data is migrated into Supabase, then chunked and embedded to build the vector index.

### Ingestion

1. **Migration** — Copy `documents`, `rdf_triples`, and `entity_aliases` from SQLite into Supabase.
2. **Chunking** — Split each document’s `full_text` into overlapping chunks (~400 tokens, 50-token overlap).
3. **Embedding** — Generate embeddings for each chunk (OpenAI `text-embedding-3-small`) and for each document’s `paragraph_summary` (stored as `summary_embedding` on chunks).
4. **Indexes** — Create pgvector `ivfflat` indexes on `chunks.embedding` and `chunks.summary_embedding` for fast approximate nearest-neighbor search.

### Retrieval — 6 stages

Each `/api/chat` request runs this pipeline in order:

1. **Query expansion**
2. **Summary-level search** — search `summary_embedding` to get a small set of candidate `doc_id`s. Optionally merge with **triple-based** candidates (doc_ids from `rdf_triples` matching actor/target/action).
3. **Chunk-level search** — Within those candidates, search the full chunk `embedding` and return the top chunks.
4. **Triple lookup** — For the doc_ids of those chunks, fetch relevant `rdf_triples`.
5. **Context assembly** — Build the LLM prompt from: retrieved chunk texts (with doc_id labels), filtered triples, and a system instruction to answer only from context and cite doc_ids.
6. **LLM generation** — Send the prompt to the LLM; return **answer**, **sources**, and **triples**.

All responses include `answer`, `sources', and `triples`; empty arrays when none.

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
2. **RPC for RAG** — `backend/ingestion/rpc_triple_candidate_doc_ids.sql`.

Then run the **ingestion pipeline** once (with `document_analysis.db` available):

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
