---
name: ""
overview: ""
todos: []
isProject: false
---

# Step 3B: Qdrant indexer — implementation plan (revised)

Scope: **indexer only**. Consume already-embedded chunks from `src/ingestion/embedding.py`. No in-memory Qdrant; persistent local storage only. Aligns with `docs/DATA_SCHEMA.md` and `docs/ARCHITECTURE.md`.

---

## 1. Collection creation (768, cosine) + existence safety

- **Where:** `src/ingestion/indexer.py` — e.g. `ensure_collection(client, collection_name, vector_size=768)`.
- **If collection does not exist:** Create with vector size 768, distance **cosine**, and payload indexes for `doc_id`, `doc_date`, `doc_type`, `page`.
- **If collection exists — safety check (mandatory):**
  - **Verify** `vector_size == expected` (768).
  - **Verify** distance metric is **cosine**.
  - **If either mismatches → raise a clear error** (e.g. `ValueError` or custom), do **not** continue silently.
  - Rationale: Changing the embedding model later (e.g. 1024 dims or different metric) would otherwise corrupt the index with no signal; failing loud prevents that.
- **Config:** Collection name from config (`QDRANT_COLLECTION`, default `epstein_files`).

---

## 2. Local persistent storage only (no in-memory)

- **Config** (`config/settings.py`): `QDRANT_PATH` (default `./data/qdrant`), `QDRANT_COLLECTION` (default `epstein_files`).
- **Client:** Use **local persistent** Qdrant only: `Qdrant(path=settings.QDRANT_PATH)`. **Do not use in-memory Qdrant.**
  - In-memory: data disappears on restart, not useful for real dev, not inspectable, breaks retrieval-over-time tests.
  - Persistent local: data survives restart, folder is inspectable, easy to move to server or migrate later.
- **Lifecycle:** Single process; client reads/writes the same path. No server process.

---

## 3. Inserting embedded chunks — payload must include `embedding_model`

- **Input:** Iterable of chunk dicts with `embedding` key (output of `embed_chunks()`), plus chunk metadata from chunking.
- **Payload for Qdrant (non-negotiable):**
  - Include all DATA_SCHEMA fields (doc_id, chunk_id, text, chunk_index, page, source_ref, doc_date, doc_type, doc_title, image_refs, entity_mentions, ingested_at).
  - **Must include `embedding_model**` in every point payload, from config (e.g. `settings.EMBED_MODEL_NAME` — e.g. `"bge-base-en-v1.5"`). This is **required** for a real system: when you change models later (bge-large, OpenAI, hybrid), you need to know which vectors came from which model; without it, debugging becomes a nightmare.
  - Do not store the vector inside the payload; store only metadata.
- **Point id:** `chunk_id` (string). Upsert in batches (e.g. 64–100 points per request). API: `client.upsert(collection_name=..., points=points_batch)`.
- **Signature:** e.g. `upsert_chunks(client, collection_name, embedded_chunks, batch_size=64)`.

---

## 4. Testing retrieval after insertion

- **Goal:** Prove indexing + retrieval work: run one semantic search after upsert.
- **Suggested:** Add `--index-test` to `scripts/run_ingestion.py`: load → chunk → embed → ensure collection → upsert → embed a fixed query (same BGE + query prefix) → `client.search(..., limit=3)` → print top 3 hits (chunk_id, doc_id, text snippet, score).
- **Query embedding:** Use same model and `EMBED_QUERY_PREFIX` + query string; single vector.

---

## 5. Avoiding duplicate inserts

- **Strategy:** Upsert with **point id = chunk_id**. Same chunk_id overwrites; new chunk_ids append. Re-runs are idempotent (replace or append). No need to check existence before upsert.

---

## Implementation order

1. **Config:** Add `QDRANT_PATH`, `QDRANT_COLLECTION` to `config/settings.py`; ensure `data/` (and `data/qdrant`) is gitignored.
2. **Indexer:** Implement `ensure_collection` (with **existence + dimension + distance check**) and `upsert_chunks` (payload **including `embedding_model**`); batch upsert; **local persistent client only**.
3. **Test:** Add `--index-test` to `scripts/run_ingestion.py`: small load → chunk → embed → index → one search, print results.
4. **Dependency:** Add `qdrant-client` to `requirements.txt` if missing.

---

## Refinements summary


| Item                           | Rule                                                                                                                    |
| ------------------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| **embedding_model in payload** | Required, non-negotiable. Set from config on every point.                                                               |
| **Qdrant storage**             | Local persistent path only (`./data/qdrant` by default). No in-memory.                                                  |
| **Collection exists**          | If collection exists: verify vector size == 768 and distance == cosine; on mismatch → **raise error**, do not continue. |


