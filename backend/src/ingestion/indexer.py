"""
Qdrant indexer: ensure collection (with dimension/distance safety), upsert embedded chunks.
Local persistent storage only; payload includes embedding_model per DATA_SCHEMA.
Qdrant local client requires point id to be a UUID; we use uuid5(chunk_id) for idempotent upserts.
"""
from __future__ import annotations

from typing import Any, Iterable, Iterator
from uuid import uuid5, NAMESPACE_DNS

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PayloadSchemaType, PointStruct, VectorParams


def _payload_from_embedded_chunk(chunk: dict[str, Any], embedding_model: str) -> dict[str, Any]:
    """Build Qdrant payload from embedded chunk; include embedding_model (required). Do not store vector in payload."""
    return {
        "doc_id": chunk.get("doc_id", ""),
        "chunk_id": chunk.get("chunk_id", ""),
        "text": chunk.get("text", ""),
        "chunk_index": chunk.get("chunk_index", 0),
        "page": chunk.get("page"),
        "source_ref": chunk.get("source_ref") or "",
        "doc_date": chunk.get("doc_date"),
        "doc_type": chunk.get("doc_type") or "",
        "doc_title": chunk.get("doc_title") or "",
        "image_refs": chunk.get("image_refs") or [],
        "entity_mentions": chunk.get("entity_mentions") or [],
        "ingested_at": chunk.get("ingested_at", ""),
        "embedding_model": embedding_model,
    }


def ensure_collection(
    client: QdrantClient,
    collection_name: str,
    vector_size: int = 768,
) -> None:
    """
    Ensure collection exists with given vector size and cosine distance.
    If it exists: verify vector_size and distance; on mismatch raise ValueError.
    If not: create with payload indexes doc_id, doc_date, doc_type, page.
    """
    exists = client.collection_exists(collection_name)
    if exists:
        info = client.get_collection(collection_name)
        params = info.config.params
        vectors_config = params.vectors
        if vectors_config is None:
            raise ValueError(
                f"Collection {collection_name!r} exists but has no vectors config; cannot verify."
            )
        # Single named vector: config can be VectorParams or dict with "default" etc.
        if hasattr(vectors_config, "size"):
            actual_size = vectors_config.size
            actual_distance = vectors_config.distance
        else:
            # Named vectors: get "default" or first
            if hasattr(vectors_config, "items"):
                # Dict-like
                first = next(iter(vectors_config.values()), None)
                if first is None:
                    raise ValueError(
                        f"Collection {collection_name!r} has no vector config entries."
                    )
                actual_size = getattr(first, "size", None)
                actual_distance = getattr(first, "distance", None)
            else:
                actual_size = getattr(vectors_config, "size", None)
                actual_distance = getattr(vectors_config, "distance", None)
        if actual_size != vector_size:
            raise ValueError(
                f"Collection {collection_name!r} exists with vector size {actual_size}, "
                f"expected {vector_size}. Change embedding model or use a new collection."
            )
        if actual_distance != Distance.COSINE:
            raise ValueError(
                f"Collection {collection_name!r} exists with distance {actual_distance}, "
                f"expected COSINE. Recreate collection or use a new one."
            )
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )
    for field, schema_type in [
        ("doc_id", PayloadSchemaType.KEYWORD),
        ("doc_date", PayloadSchemaType.KEYWORD),  # ISO date string; KEYWORD for filter
        ("doc_type", PayloadSchemaType.KEYWORD),
        ("page", PayloadSchemaType.INTEGER),
    ]:
        client.create_payload_index(
            collection_name=collection_name,
            field_name=field,
            field_schema=schema_type,
        )


def upsert_chunks(
    client: QdrantClient,
    collection_name: str,
    embedded_chunks: Iterable[dict[str, Any]],
    embedding_model: str | None = None,
    batch_size: int = 64,
    show_progress: bool = False,
) -> int:
    """
    Upsert embedded chunks into Qdrant. Point id = chunk_id. Payload includes embedding_model.
    Returns total number of points upserted.
    """
    from config import settings

    model = embedding_model if embedding_model is not None else settings.EMBED_MODEL_NAME
    batch: list[PointStruct] = []
    total = 0
    for ch in embedded_chunks:
        chunk_id = ch.get("chunk_id")
        if not chunk_id:
            continue
        vector = ch.get("embedding")
        if vector is None:
            continue
        payload = _payload_from_embedded_chunk(ch, model)
        # Qdrant local client requires UUID; deterministic from chunk_id for idempotent upserts
        point_id = uuid5(NAMESPACE_DNS, f"ragforefn.chunk.{chunk_id}")
        batch.append(
            PointStruct(
                id=point_id,
                vector=vector,
                payload=payload,
            )
        )
        if len(batch) >= batch_size:
            client.upsert(collection_name=collection_name, points=batch)
            total += len(batch)
            if show_progress:
                print(f"  upserted {total} points to {collection_name!r} ...", flush=True)
            batch = []
    if batch:
        client.upsert(collection_name=collection_name, points=batch)
        total += len(batch)
        if show_progress:
            print(f"  upserted {total} points (done).", flush=True)
    return total
