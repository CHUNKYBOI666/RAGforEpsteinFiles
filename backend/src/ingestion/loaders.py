"""
HuggingFace dataset loader. Yields document-level records (no chunking or embedding).
Each document has: doc_id, text, source_ref, doc_type, doc_title, doc_date.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterator

from datasets import load_dataset

from config.settings import HF_DATASET_NAME


# Column names used by teyler/epstein-files-20k (filename, text). Adapt if dataset schema differs.
HF_TEXT_COL = "text"
HF_FILENAME_COL = "filename"


def _doc_id_from_filename(filename: str, row_index: int) -> str:
    """Stable doc_id: prefer normalized path; fallback to hash to avoid invalid chars."""
    if not filename or not filename.strip():
        return f"row_{row_index}"
    # Filename may contain path separators; use a hash for stability and safe IDs
    normalized = filename.strip().replace("\\", "/")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


def _doc_type_from_path(filename: str) -> str:
    """Infer doc_type from path (IMAGES/ vs TEXT/)."""
    if not filename:
        return "unknown"
    path = filename.strip().replace("\\", "/").upper()
    if path.startswith("IMAGES/"):
        return "image"
    if path.startswith("TEXT/"):
        return "text"
    return "unknown"


def _doc_title_from_filename(filename: str) -> str:
    """Human-readable title: basename of path."""
    if not filename or not filename.strip():
        return ""
    return Path(filename.replace("\\", "/")).name or filename


def load_hf_documents(
    dataset_name: str | None = None,
    split: str | None = "train",
    text_col: str = HF_TEXT_COL,
    filename_col: str = HF_FILENAME_COL,
    max_docs: int | None = None,
) -> Iterator[dict[str, Any]]:
    """
    Load HuggingFace dataset and yield one document per row.

    Yields dicts with: doc_id, text, source_ref, doc_type, doc_title, doc_date.
    doc_date is None for this dataset (not provided by source).

    max_docs: if set, stop after this many documents (for testing/review).
    """
    name = dataset_name or HF_DATASET_NAME
    if split:
        ds = load_dataset(name, split=split, trust_remote_code=True)
    else:
        full = load_dataset(name, trust_remote_code=True)
        split_key = next(iter(full.keys()), "train")
        ds = full[split_key]

    for idx, row in enumerate(ds):
        if max_docs is not None and idx >= max_docs:
            return
        raw_text = row.get(text_col) or row.get("content") or ""
        text = raw_text if isinstance(raw_text, str) else str(raw_text)
        filename = row.get(filename_col) or row.get("file") or row.get("id") or ""

        if isinstance(filename, bytes):
            filename = filename.decode("utf-8", errors="replace")
        filename = str(filename).strip()

        doc_id = _doc_id_from_filename(filename, idx)
        yield {
            "doc_id": doc_id,
            "text": text,
            "source_ref": filename or "",
            "doc_type": _doc_type_from_path(filename),
            "doc_title": _doc_title_from_filename(filename),
            "doc_date": None,
        }
