# Phase 2: splits full_text into overlapping chunks (~400 tokens, 50 overlap); inserts into chunks (embedding null).

import argparse
import importlib.util
from pathlib import Path

import tiktoken
from supabase import create_client

# Load backend/.env then backend/config.py so credentials work from any cwd
_backend_dir = Path(__file__).resolve().parent.parent
_dotenv_path = _backend_dir / ".env"
if _dotenv_path.exists():
    import os
    from dotenv import load_dotenv
    load_dotenv(_dotenv_path, override=True)
_config_py = _backend_dir / "config.py"
_spec = importlib.util.spec_from_file_location("_env_config", _config_py)
_env_config = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_env_config)
SUPABASE_URL = _env_config.SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY = _env_config.SUPABASE_SERVICE_ROLE_KEY
CHUNK_SIZE = _env_config.CHUNK_SIZE
CHUNK_OVERLAP = _env_config.CHUNK_OVERLAP

BATCH_SIZE = 500


def _validate_config():
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise SystemExit(
            "Missing Supabase credentials. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
        )


def _batched(iterable, size):
    batch = []
    for x in iterable:
        batch.append(x)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def _chunk_text(encoding, text: str):
    """Split text into overlapping token windows. Returns list of chunk strings."""
    if not text or not text.strip():
        return []
    tokens = encoding.encode(text)
    if not tokens:
        return []
    step = CHUNK_SIZE - CHUNK_OVERLAP
    if step < 1:
        step = 1
    chunks = []
    start = 0
    while start < len(tokens):
        window = tokens[start : start + CHUNK_SIZE]
        chunks.append(encoding.decode(window))
        start += step
    return chunks


def _fetch_documents_paginated(supabase, page_size: int = 1000):
    offset = 0
    while True:
        resp = (
            supabase.table("documents")
            .select("doc_id, full_text")
            .order("doc_id")
            .limit(page_size)
            .offset(offset)
            .execute()
        )
        rows = resp.data or []
        print(f"  Fetched {len(rows)} documents (offset {offset}).")
        if not rows:
            return
        for r in rows:
            yield r
        if len(rows) < page_size:
            return
        offset += page_size


def main(*, reset: bool):
    _validate_config()
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    if reset:
        print("Clearing existing chunks (--reset)...")
        supabase.table("chunks").delete().gte("id", 0).execute()
        print("  Done.")
    else:
        print("Skipping chunk reset (default append mode).")

    print("Fetching documents (doc_id, full_text)...")
    encoding = tiktoken.get_encoding("cl100k_base")
    total_docs = 0
    total_docs_with_text = 0
    total_chunks = 0
    insert_buffer = []

    def flush():
        nonlocal total_chunks, insert_buffer
        if not insert_buffer:
            return
        supabase.table("chunks").insert(insert_buffer).execute()
        total_chunks += len(insert_buffer)
        insert_buffer = []

    for d in _fetch_documents_paginated(supabase, page_size=1000):
        total_docs += 1
        full_text = d.get("full_text")
        if not full_text or not str(full_text).strip():
            continue
        total_docs_with_text += 1
        doc_id = d["doc_id"]
        chunk_texts = _chunk_text(encoding, full_text)
        for i, chunk_text in enumerate(chunk_texts):
            insert_buffer.append(
                {"doc_id": doc_id, "chunk_index": i, "chunk_text": chunk_text}
            )
            if len(insert_buffer) >= BATCH_SIZE:
                flush()

    flush()
    print(
        f"Processed {total_docs_with_text} documents with non-empty full_text "
        f"(of {total_docs} total)."
    )
    print(f"Total chunks inserted: {total_chunks}.")

    print("Chunking complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear chunks table before inserting (default: append only).",
    )
    args = parser.parse_args()
    main(reset=bool(args.reset))
