"""
Set embedding and summary_embedding to NULL for all chunks so embed_chunks.py
will re-process them. Use this before re-embedding with a different model (e.g. Ollama).

Usage (from backend/):
  python -m ingestion.null_embeddings_for_reembed

Requires SUPABASE_DB_URL in .env.
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


BATCH_SIZE = 1000


def main() -> None:
    if not SUPABASE_DB_URL:
        print("SUPABASE_DB_URL is not set. Set it in backend/.env")
        raise SystemExit(1)

    total = 0
    with psycopg.connect(SUPABASE_DB_URL) as conn:
        with conn.cursor() as cur:
            while True:
                cur.execute(
                    """
                    UPDATE chunks SET embedding = NULL, summary_embedding = NULL
                    WHERE id IN (
                        SELECT id FROM chunks WHERE embedding IS NOT NULL LIMIT %s
                    );
                    """,
                    (BATCH_SIZE,),
                )
                n = cur.rowcount
                total += n
                if n == 0:
                    break
                print(f"  Nulled {n} rows (total so far: {total})")
    print(f"Set embedding and summary_embedding to NULL for {total} chunks.")
    print("Run: EMBED_PROVIDER=ollama python -m ingestion.embed_chunks --batch-size 50")


if __name__ == "__main__":
    main()
