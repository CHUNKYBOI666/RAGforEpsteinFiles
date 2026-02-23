"""
Format retrieval hits into LLM context string and citation list.
Preserves doc_id, chunk_id, page; includes image_refs for future UI.
"""
from __future__ import annotations

from typing import Any

# Hit shape from retriever: list of {"score": float, "payload": {...}}
DEFAULT_SNIPPET_MAX_CHARS = 200


def format_chunks_for_llm(hits: list[dict[str, Any]]) -> str:
    """
    Concatenate chunk texts with clear citation markers for the LLM.
    Format: --- [doc_id | chunk_id | page N] ---\\n{text}\\n
    """
    parts: list[str] = []
    for h in hits:
        payload = h.get("payload") or {}
        doc_id = payload.get("doc_id", "")
        chunk_id = payload.get("chunk_id", "")
        page = payload.get("page")
        page_str = str(page) if page is not None else "—"
        text = (payload.get("text") or "").strip()
        marker = f"--- [{doc_id} | {chunk_id} | page {page_str}] ---"
        parts.append(f"{marker}\n{text}")
    return "\n\n".join(parts) if parts else ""


def build_citations(
    hits: list[dict[str, Any]],
    snippet_max_chars: int = DEFAULT_SNIPPET_MAX_CHARS,
) -> list[dict[str, Any]]:
    """
    Build citation dicts for UI/API: doc_id, chunk_id, page, source_ref, doc_title, doc_date, doc_type, snippet, image_refs.
    Order matches hits (by score). Snippet is truncated chunk text.
    """
    citations: list[dict[str, Any]] = []
    for h in hits:
        payload = h.get("payload") or {}
        text = (payload.get("text") or "").strip()
        snippet = text
        if snippet_max_chars > 0 and len(snippet) > snippet_max_chars:
            snippet = snippet[:snippet_max_chars] + "..."
        citations.append({
            "doc_id": payload.get("doc_id", ""),
            "chunk_id": payload.get("chunk_id", ""),
            "page": payload.get("page"),
            "source_ref": payload.get("source_ref") or "",
            "doc_title": payload.get("doc_title") or "",
            "doc_date": payload.get("doc_date"),
            "doc_type": payload.get("doc_type") or "",
            "snippet": snippet,
            "score": h.get("score"),
            "image_refs": list(payload.get("image_refs") or []),
        })
    return citations


def format_retrieval_result(
    hits: list[dict[str, Any]],
    snippet_max_chars: int = DEFAULT_SNIPPET_MAX_CHARS,
) -> dict[str, Any]:
    """
    Single entry point: turn hits into context_for_llm and citations.
    Returns {"context_for_llm": str, "citations": list[dict]}.
    """
    return {
        "context_for_llm": format_chunks_for_llm(hits),
        "citations": build_citations(hits, snippet_max_chars=snippet_max_chars),
    }
