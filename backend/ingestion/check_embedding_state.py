"""
Check embedding state in the chunks table (for diagnosing empty chat retrieval).

Runs:
  - SELECT COUNT(*) FROM chunks;
  - SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL;
  - SELECT COUNT(*) FROM chunks WHERE summary_embedding IS NOT NULL;

If retrieval returns no results, compare these counts: when both non-null counts
are 0 (or tiny vs total), the vector RPCs have nothing to search.

Usage (from backend/):
  python -m ingestion.check_embedding_state

Requires SUPABASE_DB_URL in .env (same as create_indexes.py).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import psycopg

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


def main() -> None:
    if not SUPABASE_DB_URL:
        print("SUPABASE_DB_URL is not set. Set it in backend/.env to run this check.")
        print("\nOr run this SQL in the Supabase SQL editor:")
        print("  SELECT COUNT(*) AS total FROM chunks;")
        print("  SELECT COUNT(*) AS with_embedding FROM chunks WHERE embedding IS NOT NULL;")
        print("  SELECT COUNT(*) AS with_summary_embedding FROM chunks WHERE summary_embedding IS NOT NULL;")
        raise SystemExit(1)

    with psycopg.connect(SUPABASE_DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM chunks;")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL;")
            with_embedding = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM chunks WHERE summary_embedding IS NOT NULL;")
            with_summary = cur.fetchone()[0]

    print("Chunks table embedding state:")
    print(f"  Total chunks:                    {total}")
    print(f"  Chunks with embedding:           {with_embedding}")
    print(f"  Chunks with summary_embedding:   {with_summary}")
    if total and (with_embedding == 0 or with_summary == 0):
        print("\nRetrieval will return no results until embeddings are populated.")
        print("Run: python -m ingestion.embed_chunks (with EMBED_PROVIDER=ollama if using Ollama for chat).")


if __name__ == "__main__":
    main()
