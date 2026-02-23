"""Retrieval layer: search (embed + Qdrant + optional filter) and format (LLM context + citations)."""

from src.retrieval.formatter import (
    build_citations,
    format_chunks_for_llm,
    format_retrieval_result,
)
from src.retrieval.retriever import build_filter, search

__all__ = [
    "search",
    "build_filter",
    "format_retrieval_result",
    "format_chunks_for_llm",
    "build_citations",
]
