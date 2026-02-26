"""
Chunk documents from loader output into token-sized chunks with overlap.
Yields chunk payload dicts matching DATA_SCHEMA (no embeddings, no Qdrant).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterator

# Lazy-loaded BGE tokenizer for alignment with future embedding model
_TOKENIZER = None

BGE_MODEL_NAME = "BAAI/bge-base-en-v1.5"


def _get_tokenizer():
    """Load BGE tokenizer once (token counting only)."""
    global _TOKENIZER
    if _TOKENIZER is None:
        from transformers import AutoTokenizer
        _TOKENIZER = AutoTokenizer.from_pretrained(BGE_MODEL_NAME)
    return _TOKENIZER


def _non_alpha_ratio(text: str) -> float:
    """Fraction of characters that are non-alphabetic (spaces, digits, symbols). 0 if empty."""
    if not text:
        return 0.0
    non_alpha = sum(1 for c in text if not c.isalpha())
    return non_alpha / len(text)


def _alnum_ratio(text: str) -> float:
    """Fraction of characters that are alphabetic or digits. 0 if empty."""
    if not text:
        return 0.0
    alnum = sum(1 for c in text if c.isalnum())
    return alnum / len(text)


def _slice_tokens(tokenizer, text: str, chunk_size: int, overlap: int) -> Iterator[str]:
    """
    Split text into token windows of chunk_size with overlap.
    Yields decoded text for each window. Doc with 0 tokens yields nothing.
    Doc with < chunk_size tokens yields one chunk (full text).
    """
    tokens = tokenizer.encode(text, add_special_tokens=False, return_tensors=None)
    if not tokens:
        return
    step = max(1, chunk_size - overlap)
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = tokenizer.decode(chunk_tokens, skip_special_tokens=True)
        yield chunk_text
        if end >= len(tokens):
            break
        start += step


def chunk_documents(
    documents: Iterator[dict[str, Any]],
    chunk_size: int = 400,
    overlap: int = 50,
    min_doc_chars: int = 50,
    cleaning_version: str | None = None,
    min_alnum_ratio: float | None = 0.5,
    alnum_dropped: list[int] | None = None,
) -> Iterator[dict[str, Any]]:
    """
    Consume loader output and yield chunk payloads matching DATA_SCHEMA.

    - Filters out docs with empty text or len(text.strip()) < min_doc_chars.
    - Splits by tokens (BGE tokenizer) with sliding window overlap. Default 400 tokens
      keeps chunks under BGE 512-token limit after document prefix at embed time.
    - Chunks with alphanumeric ratio below min_alnum_ratio are dropped (None disables).
    - When alnum_dropped is not None (e.g. [0]), increment it for each dropped chunk.
    - Each chunk has: doc_id, chunk_id, text, chunk_index, page, source_ref,
      doc_date, doc_type, doc_title, image_refs, entity_mentions, ingested_at,
      cleaned, cleaning_version.

    cleaning_version: when not None, marks every chunk as cleaned with this version.
    documents: iterable of doc dicts (doc_id, text, source_ref, doc_type, doc_title, doc_date).
    Returns: generator of chunk payload dicts (no vectors).
    """
    tokenizer = _get_tokenizer()
    for doc in documents:
        text = doc.get("text") or ""
        if not isinstance(text, str):
            text = str(text)
        text_stripped = text.strip()
        if not text_stripped or len(text_stripped) < min_doc_chars:
            continue

        doc_id = doc.get("doc_id", "")
        source_ref = doc.get("source_ref") or ""
        doc_date = doc.get("doc_date")
        doc_type = doc.get("doc_type") or ""
        doc_title = doc.get("doc_title") or ""
        ingested_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        for chunk_index, chunk_text in enumerate(
            _slice_tokens(tokenizer, text_stripped, chunk_size, overlap)
        ):
            if min_alnum_ratio is not None and _alnum_ratio(chunk_text) < min_alnum_ratio:
                if alnum_dropped is not None:
                    alnum_dropped[0] += 1
                continue
            chunk_id = f"{doc_id}:{chunk_index}"
            yield {
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "text": chunk_text,
                "chunk_index": chunk_index,
                "page": None,
                "source_ref": source_ref,
                "doc_date": doc_date,
                "doc_type": doc_type,
                "doc_title": doc_title,
                "image_refs": [],
                "entity_mentions": [],
                "ingested_at": ingested_at,
                "cleaned": cleaning_version is not None,
                "cleaning_version": cleaning_version or "",
            }
