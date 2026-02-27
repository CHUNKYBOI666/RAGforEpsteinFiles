"""
Phase 4: creates pgvector ivfflat indexes on chunks.embedding and chunks.summary_embedding.

This is a one-off (but idempotent) script that connects directly to the Supabase
Postgres database and ensures the expected pgvector ivfflat indexes exist on the
`chunks` table. It mirrors the environment-loading pattern used by the other
ingestion scripts so it can be run from any working directory.

Usage (from backend/):

    python ingestion/create_indexes.py

Requirements:
  - backend/.env (or your shell environment) must define SUPABASE_DB_URL as the
    full Postgres connection string from the Supabase dashboard, e.g.:

      SUPABASE_DB_URL=postgresql://postgres:<password>@db.<project>.supabase.co:5432/postgres

  - The pgvector extension must already be enabled in the database and the
    `chunks` table must exist with `embedding` and `summary_embedding` columns
    of type extensions.vector(1536), as defined in schema.sql.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Sequence

import psycopg

# Load backend/.env then backend/config.py so credentials work from any cwd
_backend_dir = Path(__file__).resolve().parent.parent
_dotenv_path = _backend_dir / ".env"
if _dotenv_path.exists():
    from dotenv import load_dotenv

    load_dotenv(_dotenv_path)

_config_py = _backend_dir / "config.py"
_spec = importlib.util.spec_from_file_location("_env_config", _config_py)
_env_config = importlib.util.module_from_spec(_spec)
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(_env_config)

SUPABASE_DB_URL: str = getattr(_env_config, "SUPABASE_DB_URL", "")
SUPABASE_URL: str = getattr(_env_config, "SUPABASE_URL", "")


INDEX_QUERIES: Sequence[str] = (
    """
    CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks
      USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_chunks_summary_embedding ON chunks
      USING ivfflat (summary_embedding vector_cosine_ops) WITH (lists = 100);
    """,
)


def _validate_config() -> None:
    if not SUPABASE_DB_URL:
        raise SystemExit(
            "SUPABASE_DB_URL is not set. "
            "Set it in backend/.env (or your environment) to the full "
            "Postgres connection string from the Supabase dashboard."
        )


def _log_chunk_counts(cur: psycopg.Cursor) -> None:
    try:
        cur.execute("SELECT COUNT(*) FROM chunks;")
        total_chunks = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NULL;")
        null_embeddings = cur.fetchone()[0]
    except Exception as exc:  # noqa: BLE001
        print("Warning: failed to query chunks counts; does the table exist?")
        print(f"  Error was: {exc}")
        return

    print(f"Total chunks: {total_chunks}")
    print(f"Chunks with NULL embedding: {null_embeddings}")
    if null_embeddings == 0:
        print("All chunk embeddings are populated (embedding IS NOT NULL).")
    else:
        print(
            "Some chunks still have NULL embeddings; "
            "consider re-running embed_chunks.py before indexing."
        )


def _log_existing_indexes(cur: psycopg.Cursor) -> None:
    try:
        cur.execute(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'chunks'
            ORDER BY indexname;
            """
        )
        rows = cur.fetchall()
    except Exception as exc:  # noqa: BLE001
        print("Warning: failed to query pg_indexes for chunks.")
        print(f"  Error was: {exc}")
        return

    if not rows:
        print("No indexes found on table 'chunks' yet.")
        return

    print("Current indexes on 'chunks':")
    for name, definition in rows:
        print(f"  {name}: {definition}")


def _ensure_indexes(cur: psycopg.Cursor) -> None:
    print("Ensuring pgvector ivfflat indexes exist on chunks...")
    for idx, query in enumerate(INDEX_QUERIES, start=1):
        print(f"  [{idx}/{len(INDEX_QUERIES)}] Executing index DDL...")
        cur.execute(query)
    print("Index creation statements executed (indexes are idempotent).")


def main() -> None:
    _validate_config()

    if SUPABASE_URL:
        print(f"Connecting to Supabase Postgres for project: {SUPABASE_URL}")

    # psycopg3 connection context manager will commit on normal exit.
    with psycopg.connect(SUPABASE_DB_URL) as conn:
        with conn.cursor() as cur:
            # Optional but useful sanity checks before creating indexes.
            _log_chunk_counts(cur)

            # Show any existing indexes before changes.
            _log_existing_indexes(cur)

            # Create/ensure the ivfflat indexes.
            _ensure_indexes(cur)

            # Show indexes after changes for confirmation.
            _log_existing_indexes(cur)

    print("Done. Vector indexes on chunks should now be ready for retrieval queries.")


if __name__ == "__main__":
    main()

