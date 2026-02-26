"""
Document loaders. Yields document-level records (no chunking or embedding).
Each document has: doc_id, text, source_ref, doc_type, doc_title, doc_date.

Sources: Doc-Explorer DB (load_doc_explorer_documents), Biography Markdown (load_biography_documents).
"""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Any, Iterator


def _normalize_doc_type(category: str | None) -> str:
    """Normalize doc-explorer category to doc_type (lowercase, safe for payload)."""
    if not category or not str(category).strip():
        return "unknown"
    return str(category).strip().lower().replace(" ", "_")


def load_doc_explorer_documents(
    db_path: str | Path,
    max_docs: int | None = None,
) -> Iterator[dict[str, Any]]:
    """
    Load documents from Epstein-doc-explorer SQLite DB (document_analysis.db).

    Yields dicts with: doc_id, text, source_ref, doc_type, doc_title, doc_date.
    Skips rows with empty full_text. doc_type from category; doc_date from date_range_earliest.
    """
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"Doc-explorer DB not found: {path}")
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "SELECT doc_id, full_text, category, date_range_earliest, date_range_latest, file_path, one_sentence_summary FROM documents WHERE full_text IS NOT NULL AND full_text != ''"
        )
        for idx, row in enumerate(cur):
            if max_docs is not None and idx >= max_docs:
                break
            full_text = (row["full_text"] or "").strip()
            if not full_text:
                continue
            doc_id = row["doc_id"] or ""
            if not doc_id:
                doc_id = hashlib.sha256(full_text[:200].encode("utf-8")).hexdigest()[:32]
            if doc_id.startswith("TEXT-001-"):
                continue
            file_path = (row["file_path"] or "").strip()
            title = (row["one_sentence_summary"] or "").strip() or (Path(file_path).name if file_path else "")
            doc_date = (row["date_range_earliest"] or row["date_range_latest"] or "").strip() or None
            yield {
                "doc_id": doc_id,
                "text": full_text,
                "source_ref": file_path or "",
                "doc_type": _normalize_doc_type(row["category"]),
                "doc_title": title or doc_id,
                "doc_date": doc_date if doc_date else None,
            }
    finally:
        conn.close()


def load_biography_documents(
    biography_dir: str | Path,
    max_docs: int | None = None,
) -> Iterator[dict[str, Any]]:
    """
    Load markdown documents from epstein-biography repo (or any dir with .md files).

    Yields dicts with: doc_id, text, source_ref, doc_type, doc_title, doc_date.
    doc_type is "biography"; doc_date is None (parse frontmatter later if needed).
    """
    root = Path(biography_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"Biography dir not found: {root}")
    md_files = sorted(root.glob("**/*.md"))
    for idx, fp in enumerate(md_files):
        if max_docs is not None and idx >= max_docs:
            break
        try:
            text = fp.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            continue
        # Skip README or empty
        if fp.name.upper() == "README.MD" or not text:
            continue
        rel = fp.relative_to(root)
        path_str = str(rel).replace("\\", "/")
        doc_id = hashlib.sha256(path_str.encode("utf-8")).hexdigest()[:32]
        doc_title = fp.stem or fp.name
        yield {
            "doc_id": doc_id,
            "text": text,
            "source_ref": path_str,
            "doc_type": "biography",
            "doc_title": doc_title,
            "doc_date": None,
        }
