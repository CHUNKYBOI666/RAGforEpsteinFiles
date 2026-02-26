"""
Tests for document loaders: doc-explorer (TEXT-001- dedupe), biography.
"""
import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.ingestion.loaders import load_doc_explorer_documents


def test_text_001_duplicate_skipped():
    """Given two rows with same content where one has doc_id TEXT-001-..., only one doc is yielded (non-prefixed)."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE documents (
                doc_id TEXT,
                full_text TEXT,
                category TEXT,
                date_range_earliest TEXT,
                date_range_latest TEXT,
                file_path TEXT,
                one_sentence_summary TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO documents (doc_id, full_text, category, file_path, one_sentence_summary) VALUES (?, ?, ?, ?, ?)",
            ("HOUSE_OVERSIGHT_022780", "Same body text here. Content for the flight log.", "other", "data/001_split/HOUSE_OVERSIGHT_022780.txt", "Summary"),
        )
        conn.execute(
            "INSERT INTO documents (doc_id, full_text, category, file_path, one_sentence_summary) VALUES (?, ?, ?, ?, ?)",
            ("TEXT-001-HOUSE_OVERSIGHT_022780", "Same body text here. Content for the flight log.", "other", "data/001_split/HOUSE_OVERSIGHT_022780.txt", "Summary"),
        )
        conn.commit()
        conn.close()

        docs = list(load_doc_explorer_documents(db_path, max_docs=10))
        assert len(docs) == 1
        assert docs[0]["doc_id"] == "HOUSE_OVERSIGHT_022780"
        assert not docs[0]["doc_id"].startswith("TEXT-001-")
    finally:
        Path(db_path).unlink(missing_ok=True)
