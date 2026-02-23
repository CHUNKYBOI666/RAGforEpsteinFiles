"""
Retrieval: embed query, optional Qdrant filter, vector search. Returns hits (score + payload).
Uses embed_query from ingestion so query and document embeddings stay aligned.
"""
from __future__ import annotations

from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http.models import FieldCondition, Filter, MatchValue, Range

from src.ingestion.embedding import embed_query


def build_filter(
    *,
    doc_id: str | None = None,
    doc_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page_min: int | None = None,
    page_max: int | None = None,
) -> Filter | None:
    """
    Build a Qdrant Filter from simple retrieval params. All given conditions are ANDed (must).
    ISO date strings (doc_date) compare correctly lexicographically.
    """
    conditions: list[FieldCondition] = []
    if doc_id is not None and doc_id != "":
        conditions.append(FieldCondition(key="doc_id", match=MatchValue(value=doc_id)))
    if doc_type is not None and doc_type != "":
        conditions.append(FieldCondition(key="doc_type", match=MatchValue(value=doc_type)))
    if date_from is not None or date_to is not None:
        # doc_date is stored as ISO string (KEYWORD); lexicographic order = date order.
        # Client's Range expects float; use model_construct to pass strings to server.
        range_kw: dict[str, str] = {}
        if date_from is not None:
            range_kw["gte"] = date_from
        if date_to is not None:
            range_kw["lte"] = date_to
        conditions.append(
            FieldCondition(key="doc_date", range=Range.model_construct(**range_kw))
        )
    if page_min is not None or page_max is not None:
        range_kw = {}
        if page_min is not None:
            range_kw["gte"] = page_min
        if page_max is not None:
            range_kw["lte"] = page_max
        conditions.append(FieldCondition(key="page", range=Range(**range_kw)))
    if not conditions:
        return None
    return Filter(must=conditions)


def search(
    query: str,
    top_k: int = 20,
    *,
    client: QdrantClient | None = None,
    collection_name: str | None = None,
    query_filter: Filter | None = None,
    doc_id: str | None = None,
    doc_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page_min: int | None = None,
    page_max: int | None = None,
) -> list[dict[str, Any]]:
    """
    Embed query, run Qdrant vector search, return list of hit dicts with score and payload.
    Uses config for client path and collection if not provided (for test injection).
    Filter: pass query_filter or use doc_id/doc_type/date_from/date_to/page_min/page_max to build one.
    """
    from config import settings

    if client is None:
        settings.QDRANT_PATH.mkdir(parents=True, exist_ok=True)
        client = QdrantClient(path=str(settings.QDRANT_PATH))
    if collection_name is None:
        collection_name = settings.QDRANT_COLLECTION

    filter_to_use = query_filter
    if filter_to_use is None and any(
        x is not None
        for x in (doc_id, doc_type, date_from, date_to, page_min, page_max)
    ):
        filter_to_use = build_filter(
            doc_id=doc_id,
            doc_type=doc_type,
            date_from=date_from,
            date_to=date_to,
            page_min=page_min,
            page_max=page_max,
        )

    query_vector = embed_query(query)
    response = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        limit=top_k,
        query_filter=filter_to_use,
    )

    hits: list[dict[str, Any]] = []
    for point in response.points:
        score = getattr(point, "score", None)
        if score is None and hasattr(point, "id"):
            score = 0.0
        hits.append({"score": float(score), "payload": dict(point.payload or {})})
    return hits
