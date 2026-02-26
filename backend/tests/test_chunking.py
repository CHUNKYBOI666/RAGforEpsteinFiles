"""
Unit tests for chunking: quality filter (alnum ratio), token size defaults.
"""
import pytest

from src.ingestion.chunking import (
    _alnum_ratio,
    _non_alpha_ratio,
    chunk_documents,
)


def test_non_alpha_ratio_empty():
    assert _non_alpha_ratio("") == 0.0


def test_non_alpha_ratio_all_alpha():
    assert _non_alpha_ratio("abcdefghij") == 0.0


def test_non_alpha_ratio_half_non_alpha():
    assert _non_alpha_ratio("aaaaa%%%%%") == 0.5


def test_alnum_ratio_empty():
    assert _alnum_ratio("") == 0.0


def test_alnum_ratio_all_alnum():
    assert _alnum_ratio("abc123") == 1.0


def test_alnum_ratio_half_alnum():
    # 5 alnum, 5 symbols -> 0.5
    assert _alnum_ratio("aa111%%%%%") == 0.5


def test_alnum_ratio_below_50_percent():
    assert _alnum_ratio("aa%%%%%%%%") == 0.2


def _doc_iter(docs):
    """Turn list of doc dicts into an iterator for chunk_documents."""
    yield from docs


def test_chunk_quality_filter_drops_low_alnum():
    # Chunk with <50% alphanumeric -> dropped when min_alnum_ratio=0.5
    doc = {
        "doc_id": "test_doc",
        "text": "a" * 25 + "%" * 35,  # 25/60 < 0.5 alnum
        "source_ref": "",
        "doc_type": "other",
        "doc_title": "",
        "doc_date": None,
    }
    chunks_with_filter = list(
        chunk_documents(_doc_iter([doc]), min_alnum_ratio=0.5)
    )
    assert len(chunks_with_filter) == 0


def test_chunk_quality_filter_keeps_mostly_alnum():
    # Normal prose produces chunks that pass the filter
    doc = {
        "doc_id": "test_doc",
        "text": "The quick brown fox jumps over the lazy dog. " * 20,
        "source_ref": "",
        "doc_type": "letter",
        "doc_title": "",
        "doc_date": None,
    }
    chunks = list(chunk_documents(_doc_iter([doc]), min_alnum_ratio=0.5))
    assert len(chunks) >= 1
    for ch in chunks:
        assert _alnum_ratio(ch["text"]) >= 0.5


def test_chunk_quality_filter_disabled_when_none():
    # Same doc that would be dropped with filter on -> yielded when filter disabled
    doc = {
        "doc_id": "test_doc",
        "text": "a" * 25 + "%" * 35,
        "source_ref": "",
        "doc_type": "other",
        "doc_title": "",
        "doc_date": None,
    }
    chunks_no_filter = list(
        chunk_documents(_doc_iter([doc]), min_alnum_ratio=None)
    )
    assert len(chunks_no_filter) == 1
    assert chunks_no_filter[0]["doc_id"] == "test_doc"


def test_alnum_dropped_counter_incremented():
    """When alnum_dropped list is passed, dropped chunks increment it."""
    doc = {
        "doc_id": "test_doc",
        "text": "x" * 20 + "%" * 50,  # 20/70 < 0.5 alnum -> dropped
        "source_ref": "",
        "doc_type": "other",
        "doc_title": "",
        "doc_date": None,
    }
    dropped = [0]
    chunks = list(
        chunk_documents(_doc_iter([doc]), min_alnum_ratio=0.5, alnum_dropped=dropped)
    )
    assert len(chunks) == 0
    assert dropped[0] == 1
