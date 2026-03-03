# Epstein Document Explorer — RAG Backend Plan

## Vision

Build a conversational research tool on top of the Epstein document corpus that lets users ask natural language questions and receive precise, grounded answers with direct citations to source documents. Unlike a standard keyword search or the existing graph explorer, this system should feel like talking to a researcher who has read every document — one who can synthesize across thousands of files, name the specific actors involved, and always show their work by linking back to the original source.

The existing Epstein Doc Explorer repo (https://github.com/maxandrews/Epstein-doc-explorer) has already done the most expensive and time-consuming work: OCR, AI-powered extraction, entity deduplication, and structured relationship mapping — all stored in a single SQLite file (`document_analysis.db`). This project builds directly on top of that output. We do not re-run their pipeline. We treat their database as our starting dataset.

---

## Project Goals

1. Let users ask free-form questions about the documents and receive accurate, sourced answers
2. Every answer must cite the specific document(s) it came from, displayed as clickable source cards
3. Combine semantic (vector) search with structured (SQL) retrieval for higher precision than either alone
4. Leverage the existing relationship graph data to surface structured facts alongside text chunks
5. Be deployable, maintainable, and extensible — built with clean separation between ingestion, retrieval, and the API layer

---

## What We're Taking From the Existing Repo

The `document_analysis.db` SQLite file contains four key assets we use directly:

**`documents` table — `full_text` column**
The complete OCR-extracted and pipeline-cleaned text of every processed document. This is our RAG corpus. We chunk and embed this text to build the vector index. It is cleaner and better organized than the raw HuggingFace CSV dump because it only contains documents that successfully passed through the AI extraction pipeline, and every row is tagged with `doc_id`, `category`, and date range metadata.

**`documents` table — `paragraph_summary` column**
An AI-generated multi-sentence summary of each document, produced by Claude during the original pipeline run. We embed these summaries as a lightweight retrieval layer — they capture the document's core meaning in a compact form, making them ideal for a first-pass search before retrieving full chunks.

**`rdf_triples` table**
Structured facts extracted from every document in the form of `(actor, action, target, location, timestamp, doc_id)`. These are not used for semantic search. They are used as structured citations — when the vector search identifies relevant documents, we query their associated triples to pull out precise named facts that get injected into the LLM prompt and returned to the frontend as structured data alongside the answer.

**`entity_aliases` table**
A mapping of name variants to canonical names (e.g. "Jeff Epstein" → "Jeffrey Epstein"), produced by the deduplication step of their pipeline. We use this for query expansion — before searching, we look up all known aliases for any named entity in the user's question and include them in the search.

---

## Technology Stack

| Layer | Choice | Reason |
|---|---|---|
| Backend framework | Python + FastAPI | Async, lightweight, best AI/ML library support |
| Primary database | Supabase (PostgreSQL) | Handles both relational data and vector search via pgvector in one place, generous free tier |
| Vector search | pgvector extension on Supabase | Eliminates a separate Pinecone account, keeps everything in one DB |
| Embedding model | OpenAI `text-embedding-3-small` | Low cost (~$1 total for the full corpus), high quality, 1536 dimensions |
| LLM | Anthropic Claude (default) or OpenAI-compatible (Groq, Together, OpenRouter, vLLM, Ollama) | Set `LLM_PROVIDER=anthropic` or `openai_compatible`; Claude is strong for grounded, citation-aware answers; open-source options reduce cost at scale. |
| Data source | `document_analysis.db` from the repo | Already processed, free, MIT licensed |
| Frontend | Existing React app from the repo | Reuse their DocumentModal and timeline card components for citation UI |

---

## Database Design (Supabase)

We migrate all four tables from SQLite into Supabase and add one new table for chunks.

### `documents`
Migrated as-is from SQLite. Contains `doc_id`, `full_text`, `paragraph_summary`, `one_sentence_summary`, `category`, `date_range_earliest`, `date_range_latest`. This is the source of truth for all document metadata and text.

### `rdf_triples`
Migrated as-is from SQLite. Contains `id`, `doc_id`, `actor`, `action`, `target`, `location`, `timestamp`, `top_cluster_ids`. Foreign key on `doc_id` to `documents`. We add indexes on `actor`, `doc_id`, and `timestamp` for fast lookup.

### `entity_aliases`
Migrated as-is from SQLite. Contains `original_name` and `canonical_name`. Used purely for query expansion at retrieval time.

### `chunks` (new table)
This is the core new table we create. Each row represents a single chunk of a document's full text, with its vector embedding. Fields: `id`, `doc_id` (FK to documents), `chunk_index` (position within the document), `chunk_text` (the raw text of the chunk), `embedding` (a `VECTOR(1536)` column for pgvector), and `summary_embedding` (a second vector column storing the embedding of the parent document's `paragraph_summary`, used for the lightweight retrieval pass).

We create an `ivfflat` index on the `embedding` column using cosine distance, and a second index on `summary_embedding`, for fast approximate nearest-neighbor search.

---

## Ingestion Pipeline

This is a one-time offline process that populates Supabase from the SQLite file. It does not need to run again unless new documents are added.

### Phase 1 — Data Migration
Connect to the SQLite file and read all rows from `documents`, `rdf_triples`, and `entity_aliases`. Batch insert them into the corresponding Supabase tables. Run once. This is pure data migration with no AI calls.

### Phase 2 — Document Chunking
For each document in the `documents` table where `full_text` is not null, split the text into overlapping chunks. The target chunk size is approximately 400 tokens with a 50-token overlap between adjacent chunks. The overlap ensures that facts that span a chunk boundary are not lost. We track the `chunk_index` so chunks can be reassembled in order if needed.

### Phase 3 — Embedding Generation
For each chunk, call the OpenAI `text-embedding-3-small` model to generate a 1536-dimension embedding vector. Also generate an embedding of the parent document's `paragraph_summary` and store it on every chunk belonging to that document (as `summary_embedding`). Insert each chunk with both embeddings into the `chunks` table.

This phase is the only one with real cost. At approximately 50 million tokens for 20,000 documents, the total cost is roughly $1 using `text-embedding-3-small`. This runs once.

### Phase 4 — Index Creation
After all chunks are inserted, create the `ivfflat` vector index on both embedding columns. This enables fast approximate nearest-neighbor search at query time.

---

## Retrieval Architecture

This is the core of the RAG system. Every user query goes through a multi-stage retrieval process before reaching the LLM.

### Stage 1 — Query Expansion
Before any search happens, look up the user's query in the `entity_aliases` table. If the query contains a recognized name (or something close to one), collect all known aliases for that canonical entity. The expanded query includes all variants. This prevents missing relevant documents because a name was spelled differently.

### Stage 2 — Summary-Level Retrieval (Coarse Pass)
Embed the user's query using `text-embedding-3-small`. Run a vector similarity search against the `summary_embedding` column across all chunks. This is fast because summary embeddings represent whole documents, not fine-grained chunks. Return the top 20 candidate `doc_id` values. This narrows the search space before the more expensive fine-grained pass.

### Stage 3 — Chunk-Level Retrieval (Fine Pass)
Within the candidate `doc_id` set from Stage 2, run a second vector similarity search against the `embedding` column (full chunk embeddings). Return the top 5 most semantically similar chunks to the user's query. These are the actual text passages that will be injected into the LLM prompt.

### Stage 4 — Structured Triple Lookup
Take the `doc_id` values from the top 5 chunks. Query the `rdf_triples` table for all triples associated with those documents. Filter triples to those where the `actor` or `target` matches any term from the expanded query. These structured facts are injected into the LLM prompt separately from the chunk text — they give the model precise named facts with timestamps and locations that it can use to construct a specific, grounded answer.

### Stage 5 — Context Assembly
Assemble the LLM prompt from three parts: the retrieved chunk texts (labeled by doc_id), the filtered structured triples (formatted as bullet-point facts with source doc_ids), and the system instruction telling Claude to answer the question using only the provided context and to cite document IDs inline in its response.

### Stage 6 — LLM Generation
Send the assembled prompt to Claude. The model returns a prose answer that references specific doc_ids. The raw answer text, the list of source doc_ids, and the structured triples are all returned together in the API response.

---

## API Design

All endpoints are served by FastAPI. The API runs on port 8000.

### `GET /api/chat?q={query}`
The main RAG endpoint. Accepts a natural language question. Runs the full retrieval pipeline (Stages 1–6 above). Returns a JSON object with three fields: `answer` (the LLM's prose response), `sources` (a list of doc_id strings that were used), and `triples` (the structured facts from the rdf_triples table for those documents). The frontend uses `sources` to render source document cards and `triples` to render a timeline-style citation list — exactly matching the existing UI patterns from the doc explorer.

### `GET /api/document/{doc_id}`
Returns metadata for a single document: `doc_id`, `category`, `one_sentence_summary`, `date_range_earliest`, `date_range_latest`. Used by the frontend to populate source cards without loading full text.

### `GET /api/document/{doc_id}/text`
Returns the full text of a document. Used when the user clicks a source card to open the document viewer modal. This endpoint already exists in the original repo's Express server — we replicate it in FastAPI.

### `GET /api/search?q={query}`
Fuzzy search for actor/entity names. Returns a list of canonical entity names matching the query, along with their relationship counts. Used for the search bar in the existing graph explorer UI.

### `GET /api/tag-clusters`
Returns the 30 semantic tag clusters. Proxies the existing data so the frontend filter buttons continue to work unchanged.

### `GET /api/stats`
Returns high-level database statistics: total document count, total triple count, total chunk count, total actor count. Displayed in the sidebar.

---

## Response Format

The `/api/chat` endpoint returns a structured response designed to map directly onto the existing React UI components:

```
{
  answer: string,              // Claude's prose response with inline doc_id citations
  sources: [                   // One entry per source document used
    {
      doc_id: string,
      one_sentence_summary: string,
      category: string,
      date_range_earliest: string,
      date_range_latest: string
    }
  ],
  triples: [                   // Structured facts from those documents
    {
      actor: string,
      action: string,
      target: string,
      timestamp: string,
      location: string,
      doc_id: string
    }
  ]
}
```

The `sources` array feeds directly into the existing `DocumentModal` component. The `triples` array feeds into the existing timeline card component. No new UI components are strictly necessary to display citations — the existing doc explorer already renders both of these patterns.

---

## Project Structure

```
epstein-rag-backend/
│
├── ingestion/
│   ├── migrate_sqlite.py        # Phase 1: copies SQLite → Supabase tables
│   ├── chunk_documents.py       # Phase 2: splits full_text into chunks
│   ├── embed_chunks.py          # Phase 3: calls OpenAI, stores vectors
│   └── create_indexes.py        # Phase 4: creates pgvector ivfflat indexes
│
├── retrieval/
│   ├── query_expansion.py       # Stage 1: entity alias lookup
│   ├── summary_search.py        # Stage 2: coarse document-level search
│   ├── chunk_search.py          # Stage 3: fine chunk-level search
│   ├── triple_lookup.py         # Stage 4: structured fact retrieval
│   └── context_builder.py       # Stage 5: assembles LLM prompt
│
├── api/
│   ├── main.py                  # FastAPI app, route definitions
│   ├── chat.py                  # /api/chat endpoint, orchestrates retrieval
│   ├── documents.py             # /api/document endpoints
│   ├── search.py                # /api/search endpoint
│   └── stats.py                 # /api/stats endpoint
│
├── config.py                    # Environment variables, model names, chunk sizes
├── requirements.txt
└── README.md
```

---

## Build Order

The recommended sequence for building this, where each phase produces something testable before moving on:

**Phase 1 — Data Foundation**
Set up Supabase project. Enable pgvector. Run the SQLite migration scripts to get `documents`, `rdf_triples`, and `entity_aliases` into Supabase. At the end of this phase you have all the original data in Postgres and can run SQL queries against it.

**Phase 2 — Vector Index**
Run the chunking and embedding scripts. At the end of this phase the `chunks` table is fully populated with embeddings and the vector indexes are built. You can test raw similarity search directly in Supabase's SQL editor.

**Phase 3 — Retrieval Layer**
Build and unit-test each retrieval stage in isolation. Test query expansion against known entity names. Test summary-level search returns sensible doc candidates. Test chunk-level search returns relevant passages. Test triple lookup returns structured facts for known doc_ids. At the end of this phase you can run the full retrieval pipeline from a Python script and inspect what gets assembled before it ever touches the LLM.

**Phase 4 — LLM Integration**
Wire the assembled context into the Claude API call. Test answer quality and citation accuracy for a set of known questions whose answers are verifiable against the documents. Tune the system prompt to ensure Claude cites doc_ids consistently.

**Phase 5 — API Layer**
Wrap everything in FastAPI. Test all endpoints. Ensure the response format matches what the frontend expects.

**Phase 6 — Frontend Integration**
Add a chat input component to the existing React app. Wire `/api/chat` responses into the existing `DocumentModal` and timeline card components. The graph explorer and the RAG chat become two views on the same data.

---

## Key Constraints and Decisions

**Why two-pass retrieval (summary then chunks)?**
Embedding every chunk independently and searching all of them in one pass would work but is slower and noisier. Searching summaries first narrows the candidate document set dramatically, so the fine-grained chunk search operates over a much smaller and more relevant pool. This is the same principle as coarse-to-fine search used in production RAG systems.

**Why inject triples separately from chunks into the LLM prompt?**
Raw text chunks contain facts but in unstructured prose — the LLM has to parse them. Triples are already in `(actor, action, target)` form. Giving the LLM both means it has prose context for nuance and structured facts for precision. The answer quality is noticeably better than either alone.

**Why Supabase over Pinecone?**
Pinecone is a pure vector database. Using it means running two separate databases — Pinecone for vectors and something else for the relational data. Supabase with pgvector handles both. At the scale of 20,000 documents, pgvector performs well within Supabase's free tier. If the corpus grew to millions of documents, Pinecone would be worth revisiting.

**Why not re-run the original repo's extraction pipeline?**
The extraction pipeline makes thousands of Claude API calls and costs real money. The output is already committed to the repo as `document_analysis.db`. There is no reason to redo this work. We treat their database as a preprocessed dataset.

**Why OpenAI for embeddings but Claude for generation?**
OpenAI's `text-embedding-3-small` is the most cost-effective high-quality embedding model available. There is no meaningful benefit to using a different model for embeddings since the embedding model and the generation model do not need to be from the same provider. Claude is used for generation because it is better at producing grounded, citation-faithful answers when given structured context.

---

## Environment variables

Set these in `backend/.env` (or your environment). All credentials and URLs are env-only; see `backend/config.py` for defaults.

| Variable | Purpose |
|----------|---------|
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | Supabase project; required for DB and pgvector. |
| `SUPABASE_DB_URL` | Direct Postgres connection string for migrations/index creation. |
| `OPENAI_API_KEY`, `OPENAI_EMBED_MODEL` | Embeddings (default `text-embedding-3-small`). |
| **LLM (chat)** | |
| `LLM_PROVIDER` | `anthropic` (default) or `openai_compatible`. |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | Used when `LLM_PROVIDER=anthropic`. Model can be alias (`sonnet`, `opus`, `haiku`) or concrete ID. |
| `LLM_BASE_URL`, `LLM_MODEL` | Used when `LLM_PROVIDER=openai_compatible`. Base URL and model name for Groq, Together, OpenRouter, vLLM, Ollama, etc. |
| `LLM_API_KEY` | Optional; required by some providers (e.g. Groq, Together, OpenRouter). Leave unset or use a placeholder (e.g. `ollama`) for local servers that do not require auth. |
| `SQLITE_DB_PATH` / `DOC_EXPLORER_DB_PATH` | Path to source `document_analysis.db` for migration. |
| `CHUNK_SIZE`, `CHUNK_OVERLAP` | Chunking for ingestion. |
| `SUMMARY_TOP_K`, `TRIPLE_CANDIDATE_TOP_K`, `MAX_CANDIDATE_DOCS`, `CHUNK_TOP_K` | Retrieval pipeline tuning. |
