# Data schema (locked)

## Chunk payload (Qdrant)

Every stored chunk uses this payload. Minimal and future-proof.

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| doc_id | string | yes | Document identity; citations, grouping. |
| chunk_id | string | yes | Unique chunk id (e.g. `{doc_id}:{chunk_index}`). |
| text | string | yes | Chunk content. |
| chunk_index | int | yes | Order within document. |
| page | int \| null | no | Page number; null for emails. |
| source_ref | string | no | URL or path to original. |
| doc_date | string | no | ISO 8601 date; timeline filter. |
| doc_type | string | no | e.g. email, pdf, doc. |
| doc_title | string | no | Citation display. |
| image_refs | list[string] | no | Image IDs/URLs; Phase 3. |
| entity_mentions | list[string] | no | NER entities; person/relationship/graph later. |
| ingested_at | string | yes | ISO timestamp; reindex, debug, refresh. |
| embedding_model | string | yes | Model identifier for migrations/debug (e.g. `bge-base-en-v1.5`). |

---

## Embedding and Qdrant

- **Embedding model:** BAAI/bge-base-en-v1.5 (768 dims).
- **Collection:** `epstein_files` (env-configurable).
- **Vector:** 768, cosine.
- **Payload indexes:** doc_id, doc_date, doc_type, page.


1. Refinements
entity_mentions and ingested_at are in the schema and doc; both are useful and low-cost.
2. Final chunk payload schema (locked)
Field	Type	Required	Purpose
doc_id	string	yes	Document identity
chunk_id	string	yes	Unique chunk id
text	string	yes	Chunk content
chunk_index	int	yes	Order in doc
page	int \	null	no	Page number
source_ref	string	no	URL/path to original
doc_date	string	no	ISO date; timeline
doc_type	string	no	email, pdf, etc.
doc_title	string	no	Citation display
image_refs	list[string]	no	Phase 3
entity_mentions	list[string]	no	NER; person/graph later
ingested_at	string	yes	ISO timestamp; reindex/debug
3. Embedding + Qdrant (confirmed)
Model: BAAI/bge-base-en-v1.5
Collection: epstein_files
Vector: 768, cosine
Payload indexes: doc_id, doc_date, doc_type, page
Step 1 implemented (HF loader only)
docs/SCHEMA_AND_DESIGN.md – Locked schema + embedding/Qdrant (including entity_mentions, ingested_at).
config/settings.py – HF_DATASET_NAME, DATA_DIR from env.
src/ingestion/loaders.py – load_hf_documents(): loads teyler/epstein-files-20k, yields doc_id, text, source_ref, doc_type, doc_title, doc_date (None). Optional max_docs for tests. Handles missing "train" split and alternate column names.
scripts/run_ingestion.py – Calls loader with max_docs=10, prints first few docs and count.
requirements.txt – datasets, python-dotenv.
.env.example, .gitignore.
Run (after pip install -r requirements.txt):
cd /Users/bombasticbombaclat/Desktop/Stuff/RAGforEFN && python scripts/run_ingestion.py
First run will download the dataset from HuggingFace. For a full run, set max_docs=None in the script or pass it from the caller.
No chunking, embedding, or Qdrant in this step. Ready for your review before we add the next step.

doc_id must be globally stable and deterministic.
Use source-provided ID if available.
If missing: generate stable hash of source + title + index.

Qdrant collection: epstein_files
Schema version: v1
