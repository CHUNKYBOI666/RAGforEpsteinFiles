# Phase 3: calls OpenAI text-embedding-3-small, stores chunk + summary_embedding in Supabase chunks table.

import argparse
import importlib.util
from pathlib import Path
from time import sleep
from typing import Dict, List, Optional, Sequence, Tuple

from openai import OpenAI
from supabase import create_client

# Load backend/.env then backend/config.py so credentials work from any cwd
_backend_dir = Path(__file__).resolve().parent.parent
_dotenv_path = _backend_dir / ".env"
if _dotenv_path.exists():
    from dotenv import load_dotenv

    load_dotenv(_dotenv_path, override=True)

_config_py = _backend_dir / "config.py"
_spec = importlib.util.spec_from_file_location("_env_config", _config_py)
_env_config = importlib.util.module_from_spec(_spec)
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(_env_config)

SUPABASE_URL: str = _env_config.SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY: str = _env_config.SUPABASE_SERVICE_ROLE_KEY
SUPABASE_DB_URL: str = getattr(_env_config, "SUPABASE_DB_URL", "")
OPENAI_API_KEY: str = _env_config.OPENAI_API_KEY
OPENAI_EMBED_MODEL: str = _env_config.OPENAI_EMBED_MODEL

BATCH_SIZE_DEFAULT = 100
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2.0


def _mask_api_key(key: str) -> str:
    """Return a safe mask for logging: prefix (e.g. sk-proj-) and last 4 chars."""
    if not key or len(key) < 8:
        return "(not set or too short)"
    return f"{key[:7]}...{key[-4:]}"


def _validate_config() -> None:
    missing = []
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_SERVICE_ROLE_KEY:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")
    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")
    if missing:
        joined = ", ".join(missing)
        raise SystemExit(
            f"Missing required configuration values: {joined}. "
            "Set them in backend/.env or your environment."
        )


def _create_supabase_client():
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def _create_openai_client() -> OpenAI:
    return OpenAI(api_key=OPENAI_API_KEY)


def _vector_to_pg(vec: List[float]) -> str:
    """Format a list of floats as a pgvector literal: '[x,y,z,...]'."""
    return "[" + ",".join(str(x) for x in vec) + "]"


def _upsert_chunks_via_db(updates: List[dict]) -> None:
    """Upsert chunk rows via direct Postgres connection with raised statement_timeout.
    Requires SUPABASE_DB_URL. Uses psycopg so the single upsert can run up to 120s.
    """
    import psycopg
    if not SUPABASE_DB_URL:
        raise RuntimeError("SUPABASE_DB_URL is required for _upsert_chunks_via_db")
    with psycopg.connect(SUPABASE_DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '120s'")
            for row in updates:
                emb_str = _vector_to_pg(row["embedding"])
                sum_emb = row.get("summary_embedding")
                sum_emb_str = _vector_to_pg(sum_emb) if sum_emb is not None else None
                cur.execute(
                    """
                    INSERT INTO chunks (id, doc_id, chunk_index, chunk_text, embedding, summary_embedding)
                    VALUES (%s, %s, %s, %s, %s::extensions.vector, %s::extensions.vector)
                    ON CONFLICT (id) DO UPDATE SET
                        doc_id = EXCLUDED.doc_id,
                        chunk_index = EXCLUDED.chunk_index,
                        chunk_text = EXCLUDED.chunk_text,
                        embedding = EXCLUDED.embedding,
                        summary_embedding = EXCLUDED.summary_embedding
                    """,
                    (
                        row["id"],
                        row["doc_id"],
                        row["chunk_index"],
                        row["chunk_text"],
                        emb_str,
                        sum_emb_str,
                    ),
                )
        conn.commit()


def _fetch_embedding_counts() -> Optional[Tuple[int, int]]:
    """Return (total_chunks, pending_null_count) if SUPABASE_DB_URL is set, else None."""
    if not SUPABASE_DB_URL:
        return None
    try:
        import psycopg
        with psycopg.connect(SUPABASE_DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM chunks;")
                total = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NULL;")
                pending = cur.fetchone()[0]
                return (total, pending)
    except Exception as exc:  # noqa: BLE001
        print(f"  (Could not fetch counts for progress: {exc})")
        return None


def _fetch_pending_chunks(
    supabase, batch_size: int, last_id: Optional[int]
) -> List[dict]:
    """Fetch up to `batch_size` chunks where embedding IS NULL, after last_id."""
    query = (
        supabase.table("chunks")
        .select("id, doc_id, chunk_index, chunk_text")
        .is_("embedding", "null")
    )
    if last_id is not None:
        query = query.gt("id", last_id)
    resp = query.order("id").limit(batch_size).execute()
    return resp.data or []


def _fetch_paragraph_summaries(
    supabase, doc_ids: Sequence[str]
) -> Dict[str, Optional[str]]:
    """Return mapping of doc_id -> paragraph_summary (may be empty or None)."""
    if not doc_ids:
        return {}
    unique_ids = sorted(set(doc_ids))
    resp = (
        supabase.table("documents")
        .select("doc_id, paragraph_summary")
        .in_("doc_id", unique_ids)
        .execute()
    )
    rows = resp.data or []
    summaries: Dict[str, Optional[str]] = {}
    for row in rows:
        summaries[row["doc_id"]] = row.get("paragraph_summary")
    return summaries


def _embed_texts(
    client: OpenAI, texts: Sequence[str], *, max_retries: int = MAX_RETRIES
) -> List[List[float]]:
    """Call OpenAI embeddings API for a list of texts, with basic retry."""
    if not texts:
        return []

    attempt = 0
    while True:
        try:
            response = client.embeddings.create(
                model=OPENAI_EMBED_MODEL,
                input=list(texts),
            )
            return [item.embedding for item in response.data]
        except Exception as exc:  # noqa: BLE001
            attempt += 1
            if attempt > max_retries:
                raise RuntimeError(
                    f"OpenAI embeddings failed after {max_retries} retries"
                ) from exc
            sleep(RETRY_BACKOFF_SECONDS * attempt)


def _process_batch(
    supabase,
    client: OpenAI,
    batch_size: int,
    batch_index: int,
    last_id: Optional[int],
) -> tuple[int, Optional[int]]:
    """Fetch one batch of chunks, embed, and update.

    Returns (processed_count, max_id_seen).
    """
    rows = _fetch_pending_chunks(supabase, batch_size=batch_size, last_id=last_id)
    if not rows:
        return 0, last_id

    print(f"Processing batch {batch_index} with {len(rows)} chunks...")

    chunk_ids: List[int] = [row["id"] for row in rows]
    doc_ids: List[str] = [row["doc_id"] for row in rows]
    chunk_texts: List[str] = [row.get("chunk_text") or "" for row in rows]

    # Fetch paragraph summaries for parent documents.
    summaries_by_doc = _fetch_paragraph_summaries(supabase, doc_ids)

    # Prepare unique non-empty summaries for embedding.
    summary_inputs: List[str] = []
    summary_doc_ids: List[str] = []
    for doc_id, summary in summaries_by_doc.items():
        if summary and str(summary).strip():
            summary_inputs.append(str(summary))
            summary_doc_ids.append(doc_id)

    summary_embeddings: List[List[float]] = []
    if summary_inputs:
        summary_embeddings = _embed_texts(client, summary_inputs)

    doc_id_to_summary_embedding: Dict[str, List[float]] = {}
    for doc_id, emb in zip(summary_doc_ids, summary_embeddings):
        doc_id_to_summary_embedding[doc_id] = emb

    # Embed all chunk texts for this batch.
    chunk_embeddings = _embed_texts(client, chunk_texts)
    if len(chunk_embeddings) != len(chunk_ids):
        raise RuntimeError(
            "Chunk embeddings length mismatch; "
            f"expected {len(chunk_ids)}, got {len(chunk_embeddings)}"
        )

    updates = []
    missing_summary_docs = set()
    for idx, row in enumerate(rows):
        doc_id = row["doc_id"]
        chunk_id = row["id"]
        chunk_embedding = chunk_embeddings[idx]
        summary_embedding = doc_id_to_summary_embedding.get(doc_id)
        if summary_embedding is None:
            missing_summary_docs.add(doc_id)

        update_payload = {
            "id": chunk_id,
            "doc_id": row["doc_id"],
            "chunk_index": row["chunk_index"],
            "chunk_text": row["chunk_text"],
            "embedding": chunk_embedding,
        }
        if summary_embedding is not None:
            update_payload["summary_embedding"] = summary_embedding
        updates.append(update_payload)

    if SUPABASE_DB_URL:
        _upsert_chunks_via_db(updates)
    else:
        # Without SUPABASE_DB_URL we use the Supabase REST client; large batches
        # may hit statement timeout—use a smaller --batch-size (e.g. 50) if needed.
        supabase.table("chunks").upsert(updates).execute()

    if missing_summary_docs:
        # Just log once per batch; chunks still get their own embeddings.
        print(
            f"  Warning: {len(missing_summary_docs)} documents in this batch "
            "have no paragraph_summary; summary_embedding left NULL."
        )

    max_id = max(row["id"] for row in rows)
    return len(rows), max_id


def _print_progress(
    total_processed: int,
    batch_index: int,
    processed_this_batch: int,
    total_chunks: Optional[int],
    pending_count: Optional[int],
) -> None:
    """Print one line of progress (processed so far, %, remaining when counts known)."""
    if pending_count is not None and total_chunks is not None:
        pct = (100.0 * total_processed / pending_count) if pending_count else 100.0
        remaining = max(0, pending_count - total_processed)
        print(
            f"  Progress: {total_processed:,} / {pending_count:,} chunks ({pct:.1f}%) "
            f"| batch {batch_index} | {processed_this_batch} this batch | {remaining:,} remaining"
        )
    else:
        print(
            f"  Progress: {total_processed:,} chunks done so far | batch {batch_index} | "
            f"{processed_this_batch} this batch"
        )


def main(batch_size: int = BATCH_SIZE_DEFAULT, max_batches: Optional[int] = None) -> None:
    _validate_config()
    print(f"Using OPENAI_API_KEY: {_mask_api_key(OPENAI_API_KEY)}")

    supabase = _create_supabase_client()
    client = _create_openai_client()

    # Optional: get total and pending counts for progress (requires SUPABASE_DB_URL)
    counts = _fetch_embedding_counts()
    total_chunks: Optional[int] = None
    pending_count: Optional[int] = None
    if counts is not None:
        total_chunks, pending_count = counts
        print(
            f"Chunks: {total_chunks:,} total, {pending_count:,} pending (embedding IS NULL)."
        )
    else:
        print("Chunks: total/pending unknown (set SUPABASE_DB_URL in .env for progress %).")

    total_processed = 0
    batch_index = 1
    last_id: Optional[int] = None

    print(
        f"Starting embedding job with batch_size={batch_size}, "
        f"model={OPENAI_EMBED_MODEL}."
    )

    while True:
        if max_batches is not None and batch_index > max_batches:
            print(
                f"Reached max_batches={max_batches}. "
                f"Total chunks processed: {total_processed:,}."
            )
            break

        processed, last_id = _process_batch(
            supabase, client, batch_size, batch_index, last_id
        )
        if processed == 0:
            print(
                f"No more chunks with NULL embeddings. "
                f"Total chunks processed: {total_processed:,}."
            )
            break

        total_processed += processed
        _print_progress(
            total_processed, batch_index, processed, total_chunks, pending_count
        )
        batch_index += 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Phase 3: generate embeddings for chunks where embedding IS NULL "
            "and store both chunk and summary embeddings in Supabase."
        )
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE_DEFAULT,
        help=(
            "Number of chunks to embed per batch (default: "
            f"{BATCH_SIZE_DEFAULT})."
        ),
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=None,
        help="Optional maximum number of batches to process (default: no limit).",
    )
    args = parser.parse_args()
    main(batch_size=args.batch_size, max_batches=args.max_batches)

