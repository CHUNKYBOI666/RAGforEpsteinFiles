# Project architecture

## High-level

```
INGESTION (offline / CLI)          SERVING (online)
┌────────────────────────┐        ┌──────────────┐  ┌─────────────────┐
│ Doc-explorer DB +       │──► Chunk ──► Embed ──►│ Qdrant           │  │ FastAPI         │
│ Biography Markdown      │        └───────┬──────┘  │ /search, /chat  │
│ (optional: HF via flag) │                 │         └────────┬────────┘
└────────────────────────┘                 ▼                  ▼
                                    ┌───────────────┐  ┌─────────────────┐
                                    │ Vector Store  │◄─│ LLM (answer +   │
                                    │ (Qdrant)      │  │ citations)      │
                                    └───────────────┘  └─────────────────┘
```

- **Ingestion**: one-way pipeline (doc-explorer + biography by default → chunk → embed → Qdrant). Run as script/CLI; `--source hf` for HuggingFace.
- **Serving**: FastAPI reads from Qdrant and calls LLM for answers; retrieval supports optional filters (date_from, date_to, doc_type).

---

## Folder structure

```
RAGforEFN/
├── PROJECT_CONTEXT.md
├── config/
│   └── settings.py
├── src/
│   ├── ingestion/       # offline pipeline
│   │   ├── loaders.py
│   │   ├── chunking.py
│   │   ├── embedding.py
│   │   └── indexer.py
│   ├── retrieval/
│   │   ├── retriever.py
│   │   └── formatter.py
│   ├── api/
│   │   ├── app.py
│   │   └── routes/
│   └── models/
├── scripts/
│   └── run_ingestion.py
├── data/
└── docs/
```

---

## Ingestion flow

1. **Load** — Read doc-explorer SQLite (document_analysis.db) and/or biography Markdown (epstein-biography/*.md); optional HuggingFace. Normalize to (id, text, metadata) per document.
2. **Chunk** — Split text into chunks; attach doc_id, chunk_index, page, source_ref, doc_date, doc_type, doc_title, entity_mentions (optional), ingested_at.
3. **Embed** — Batch chunks through embedding model → one vector per chunk.
4. **Index** — Upsert (chunk_id, vector, payload) into Qdrant; create collection if missing, payload indexes on filter fields.

---

## Embedding pipeline

- **Input**: list of chunks (text + metadata).
- **Model**: single embedding model for index and query (see DATA_SCHEMA.md).
- **Process**: batch chunks → encode → attach vector per chunk.
- **Output**: chunks with `embedding`; indexer persists to Qdrant.

---

## Retrieval pipeline

1. **Query** — User question or search string via FastAPI.
2. **Embed query** — Same model as ingestion; one vector per request.
3. **Vector search** — Qdrant top-k with payload (text + metadata).
4. **Response** — Search: return hits. Chat: pass hits + query to LLM → answer + citations.

Retrieval Modes (future):

1. Semantic search
2. Entity search (person-based)
3. Timeline search
4. Document browse mode

Phase 1 implements semantic only.