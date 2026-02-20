# Phase 3: Embedding + Qdrant Indexing — Implementation Plan (refined)

**Context:** Chunking pipeline is done. We add embedding and Qdrant indexing in strict sub-steps with review gates.

---

## Refinements applied

1. **Embedding prefix (BGE recommended)**  
   - Documents: `Represent this document for retrieval: {text}`  
   - Queries (later): `Represent this question for retrieving relevant documents: {query}`  
   - Document prefix applied during embedding step; configurable in settings.

2. **Payload: store embedding model name**  
   - Add `embedding_model: "bge-base-en-v1.5"` to each point payload for migrations and debugging.

3. **Qdrant storage**  
   - Default: **local persistent** only.  
   - Use `Qdrant(path="./data/qdrant")` (no in-memory default). Data survives restart and is inspectable.

4. **Verification script**  
   - After a small test run: run one semantic search (e.g. query `"flight log"`, top 3 chunks) to confirm embedding + Qdrant end-to-end.

5. **Implementation order (strict)**  
   - **Step 3A** — Embedding module only (test on 10 chunks). **STOP for review.**  
   - **Step 3B** — Qdrant indexer only (test insert + fetch). **STOP for review.**  
   - **Step 3C** — Full pipeline wiring (load → chunk → embed → index). **STOP for review.**  
   - Do not build everything at once.

---

## Step 3A — Embedding module only

- **Config (settings):**  
  - `EMBED_DOCUMENT_PREFIX` (default: `Represent this document for retrieval: `)  
  - `EMBED_QUERY_PREFIX` (default: `Represent this question for retrieving relevant documents: `) for future retrieval  
  - `EMBED_MODEL_NAME` (default: `bge-base-en-v1.5`) for payload and model load  
- **Module:** `src/ingestion/embedding.py`  
  - Load BGE via sentence-transformers; apply document prefix from config; batch encode; yield chunks with `embedding` key.  
  - Device: auto (cuda → mps → cpu); optional env override.  
- **Test:** Run embedding on 10 chunks (e.g. from loader → chunk, take 10), print shape / one vector. No Qdrant.

---

## Step 3B — Qdrant indexer only

- **Config:** `QDRANT_PATH` default `./data/qdrant`, `QDRANT_COLLECTION` default `epstein_files`.  
- **Storage:** Local persistent only. **Do not use in-memory Qdrant.**  
- **Module:** `src/ingestion/indexer.py`  
  - `ensure_collection(client, collection_name, vector_size=768)`: if collection exists, **verify** vector size and distance (cosine); **if mismatch → raise error**. If missing, create with payload indexes: doc_id, doc_date, doc_type, page.  
  - Upsert in batches; point id = chunk_id; payload **must** include schema + `embedding_model` (required for future model migrations/debugging).  
- **Test:** Insert a few points (e.g. mock chunks with vectors), fetch by id, then one semantic search.

---

## Step 3C — Full pipeline + verification

- Wire: load → chunk → embed → index in `scripts/run_ingestion.py` (e.g. `--embed-index`, `--max-docs`).  
- Verification script: after small run, run one semantic search (query `"flight log"`, top 3), print results to confirm end-to-end.

---

## Schema / config summary

- **Payload:** Existing DATA_SCHEMA fields + `embedding_model` (string, e.g. `"bge-base-en-v1.5"`).  
- **Qdrant:** Local only, `path="./data/qdrant"` by default.  
- **Prefixes:** Configurable; document prefix used in embedding step so retrieval is optimal later.
