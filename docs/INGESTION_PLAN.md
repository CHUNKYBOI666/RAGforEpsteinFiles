# Ingestion plan

Incremental steps. Do not build the entire pipeline at once.

---

## Step 1: Document loaders — DONE

- **Doc-explorer:** Load `document_analysis.db` (Epstein-doc-explorer repo). Obtain DB: clone repo and download via Git LFS or from GitHub media URL. Yield doc_id, text, source_ref, doc_type (from category), doc_title, doc_date (from date_range_earliest/latest).
- **Biography:** Load Markdown from epstein-biography repo (`BIOGRAPHY_DIR`); glob `**/*.md`; doc_type=biography.
- **Default source:** both (doc-explorer then biography). Optional: `--source hf` for HuggingFace `teyler/epstein-files-20k`.
- **Code:** `src/ingestion/loaders.py`, `scripts/run_ingestion.py`, `config/settings.py` (DOC_EXPLORER_DB_PATH, BIOGRAPHY_DIR).

---

## Step 2: Chunking — DONE

- Consume loader output; split text into chunks (size + overlap or sentence-aware).
- Attach metadata per chunk to match payload schema (doc_id, chunk_index, source_ref, doc_type, doc_title, doc_date, page=null, image_refs=[], entity_mentions=[], ingested_at=now).
- Output: list of chunk objects (text + metadata), no vectors.

---

## Step 3: Embedding + indexer — DONE

- Create Qdrant collection if missing: name, 768 dims, cosine, payload indexes (doc_id, doc_date, doc_type, page).
- Batch chunks → embed (bge-base-en-v1.5) → upsert to Qdrant with chunk_id as point id, full payload.
- Idempotent: re-run replaces or appends by design.

---

## Step 4: Wire full pipeline (script) — DONE

- Run: load → chunk → embed → index in one script.
- Optional: limit docs for testing (max_docs), then full run.

---

## Later phases

- Citation system: doc id, page, source link (schema already supports).
- Image linking: populate image_refs (Phase 3).
- NER: populate entity_mentions for person/relationship/graph features.

Each step must be independently testable.
Do not combine steps until validated.