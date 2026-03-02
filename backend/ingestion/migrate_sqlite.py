# Phase 1: copies SQLite (document_analysis.db) → Supabase tables (documents, rdf_triples, entity_aliases).
# Single exception to "no SQLite in codebase": this one-off migration script only.

import importlib.util
import sqlite3
from pathlib import Path

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
SQLITE_DB_PATH = _env_config.SQLITE_DB_PATH

BATCH_SIZE = 500

# Supabase column names (schema is source of truth)
DOCUMENTS_COLS = [
    "doc_id",
    "full_text",
    "paragraph_summary",
    "one_sentence_summary",
    "category",
    "date_range_earliest",
    "date_range_latest",
]
RDF_TRIPLES_COLS = [
    "id",
    "doc_id",
    "actor",
    "action",
    "target",
    "location",
    "timestamp",
    "top_cluster_ids",
]
ENTITY_ALIASES_COLS = ["original_name", "canonical_name"]


def _row_to_dict(cursor, row):
    return {cursor.description[i][0]: row[i] for i in range(len(row))}


def _batched(iterable, size):
    batch = []
    for x in iterable:
        batch.append(x)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def _validate_config():
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise SystemExit(
            "Missing Supabase credentials. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
        )
    path = Path(SQLITE_DB_PATH)
    if not path.is_file():
        raise SystemExit(
            f"SQLite database not found or not a file: {path}. Set SQLITE_DB_PATH or DOC_EXPLORER_DB_PATH."
        )
    return path


def _read_table(conn, table, columns):
    col_list = ", ".join(columns)
    cursor = conn.execute(f"SELECT {col_list} FROM {table}")
    rows = []
    while True:
        row = cursor.fetchone()
        if row is None:
            break
        rows.append(_row_to_dict(cursor, row))
    return rows


def main():
    db_path = _validate_config()
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    conn = sqlite3.connect(str(db_path))
    try:
        # 1. documents (no FK deps)
        print("Reading documents...")
        documents = _read_table(conn, "documents", DOCUMENTS_COLS)
        print(f"  {len(documents)} rows.")
        for i, batch in enumerate(_batched(documents, BATCH_SIZE)):
            supabase.table("documents").insert(batch).execute()
            print(f"  Inserted batch {i + 1} ({len(batch)} rows).")

        # 2. rdf_triples (FK doc_id → documents); only insert triples whose doc_id exists in documents
        doc_ids = {d["doc_id"] for d in documents}
        print("Reading rdf_triples...")
        rdf_triples_raw = _read_table(conn, "rdf_triples", RDF_TRIPLES_COLS)
        rdf_triples = [r for r in rdf_triples_raw if r["doc_id"] in doc_ids]
        skipped = len(rdf_triples_raw) - len(rdf_triples)
        if skipped:
            print(f"  Skipped {skipped} triples with missing doc_id.")
        print(f"  {len(rdf_triples)} rows.")
        for i, batch in enumerate(_batched(rdf_triples, BATCH_SIZE)):
            supabase.table("rdf_triples").insert(batch).execute()
            print(f"  Inserted batch {i + 1} ({len(batch)} rows).")

        # 3. entity_aliases
        print("Reading entity_aliases...")
        entity_aliases = _read_table(conn, "entity_aliases", ENTITY_ALIASES_COLS)
        print(f"  {len(entity_aliases)} rows.")
        for i, batch in enumerate(_batched(entity_aliases, BATCH_SIZE)):
            supabase.table("entity_aliases").insert(batch).execute()
            print(f"  Inserted batch {i + 1} ({len(batch)} rows).")
    finally:
        conn.close()

    print("Migration complete.")


if __name__ == "__main__":
    main()
