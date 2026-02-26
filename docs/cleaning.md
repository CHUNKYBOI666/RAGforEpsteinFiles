# Document cleaning layer

Design and behavior of the cleaning layer used between Load and Chunk in ingestion.

---

## 1. Goals and philosophy

We are building an accurate semantic search engine.

The cleaning layer must:

- Maximize semantic clarity for embeddings
- Remove structural noise and OCR damage
- Preserve factual meaning
- Preserve document identity for citation
- Improve retrieval accuracy

We are NOT optimizing for:

- Legal-grade exact quoting
- Visual fidelity to original formatting
- Perfect reconstruction of PDFs

We care about: **meaning clarity + document attribution.**

### Philosophy

The cleaner should transform messy document text into:

- Clear, semantically coherent natural language
- Optimized for embedding models

We prioritize:

- Readable paragraphs
- Complete sentences
- Minimal OCR artifacts
- No navigation junk
- No repeated headers/footers

We accept:

- Minor wording normalization
- Repair of broken OCR words
- Aggressive removal of structural noise

---

## 2. Implementation (v3)

- **Where:** [backend/src/ingestion/cleaning.py](backend/src/ingestion/cleaning.py). `CLEANING_VERSION = "v3"`.
- **Public API:** `clean_document(doc)`, `clean_text(text, config)`, `CleaningConfig`, `get_config_for_doc_type(doc_type)`.
- **When:** Between Load and Chunk when `ENABLE_DOCUMENT_CLEANING` is true (default). See [INGESTION_PLAN.md](INGESTION_PLAN.md).

### Pipeline summary

1. Normalize encoding (NFKC), collapse whitespace.
2. Split into lines.
3. **Doc-type branch:**
   - **financial_document:** Drop only known boilerplate (OMB, Page N of N). No line joining, no aggressive drop. Preserve tabular rows.
   - **book_excerpt:** Join OCR column fragments (lowercase 3–10 char start of line → previous line), then full cleaning.
   - **court_filing, letter, biography, media_article, default/unknown:** Full cleaning: join continuation lines, strip line-edge punctuation, drop OCR/header/dedupe/short lines.
4. Rejoin lines, collapse whitespace.

### Doc-type behavior

| doc_type           | Line join | OCR fragment join | Aggressive drop | Notes                |
|--------------------|-----------|--------------------|-----------------|----------------------|
| financial_document | No        | No                 | No              | Boilerplate only     |
| book_excerpt       | Yes       | Yes                | Yes             | Column-split repair  |
| court_filing, letter, biography, media_article | Yes | No | Yes | Default v3 behavior  |
| unknown / None     | Yes       | No                 | Yes             | Same as default      |

### Requirement → v3 behavior

| Doc requirement                         | How v3 does it                                                                 |
|----------------------------------------|--------------------------------------------------------------------------------|
| Maximize semantic clarity               | Line-join continuation lines; OCR column-fragment join (book_excerpt); strip line-edge punctuation; drop OCR/header/short. |
| Remove structural noise and OCR damage  | OCR noise filter; header-like drop; dedupe repeated lines; financial boilerplate-only. |
| Preserve factual meaning                | Conservative path for financial_document; keep_patterns (dates, @, list items). |
| Preserve document identity              | clean_document only updates doc["text"] and metrics; doc_id/source_ref/doc_type unchanged. |
| Readable paragraphs, complete sentences| join_continuation_lines; join_ocr_column_fragments.                           |
| Minimal OCR artifacts                  | strip_line_edge_punctuation; drop_ocr_lines; column-fragment repair.           |
| No nav junk / repeated headers-footers | drop_header_like_lines; dedupe_repeated_lines; drop_financial_boilerplate_only. |
| Repair broken OCR words                 | book_excerpt: join_ocr_column_fragments (e.g. int + ernational → international). |
| Aggressive removal of structural noise  | Default: ocr_noise_ratio 0.30, min_line_chars 30, header drop, short-line drop. |

---

## 3. Versioning and re-ingestion

- Chunk payload includes `cleaning_version` (e.g. `v3`) for tracking.
- After changing the cleaning pipeline or presets, re-run full ingestion (or per-source) to refresh Qdrant chunks. No schema change required.

---

## 4. Gaps / future work

- More financial boilerplate patterns (e.g. form-specific headers).
- Additional doc_type presets if new categories appear in the corpus.
- Tuning thresholds (ocr_noise_ratio, min_line_chars) per doc_type based on retention/quality metrics.

---

## How to test quality

- Run: `cd backend && PYTHONPATH=. python scripts/test_cleaning.py --max-docs 10 --source both`
- Inspect BEFORE/AFTER previews and overall retention (target: 5–25% removal for OCR-heavy docs; financial_document should retain most content).
- After re-ingestion, compare retrieval quality (e.g. search/chat over sample queries).
