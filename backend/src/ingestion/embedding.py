"""
Batch-embed chunks with BGE. Applies configurable document prefix for retrieval.
Yields chunk dicts with an "embedding" key (list of float, 768 dims).
"""
from __future__ import annotations

from typing import Any, Iterable, Iterator

# HF name for loading; payload uses config EMBED_MODEL_NAME (short name)
BGE_HF_NAME = "BAAI/bge-base-en-v1.5"

_encoder = None


def _get_encoder():
    """Load BGE model once per process."""
    global _encoder
    if _encoder is None:
        from sentence_transformers import SentenceTransformer

        from config import settings

        device = settings.EMBED_DEVICE
        if not device:
            import torch
            if torch.cuda.is_available():
                device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        _encoder = SentenceTransformer(BGE_HF_NAME, device=device)
    return _encoder


def _apply_document_prefix(text: str, prefix: str) -> str:
    """Prefix text with BGE document instruction for retrieval."""
    return prefix + text if text else text


def embed_chunks(
    chunks: Iterable[dict[str, Any]],
    batch_size: int | None = None,
    device: str | None = None,
    show_progress: bool = False,
) -> Iterator[dict[str, Any]]:
    """
    Embed chunk texts in batches; yield same chunk dicts with "embedding" key.

    Uses EMBED_DOCUMENT_PREFIX from config. Batch size from config if not passed.
    If show_progress=True, prints progress every 10 batches (requires consuming iterator).
    """
    from config import settings

    prefix = settings.EMBED_DOCUMENT_PREFIX
    size = batch_size if batch_size is not None else settings.EMBED_BATCH_SIZE
    encoder = _get_encoder()
    if device and encoder.device.type != device:
        encoder = encoder.to(device)

    batch: list[dict[str, Any]] = []
    texts: list[str] = []
    total_yielded = 0

    for ch in chunks:
        text = (ch.get("text") or "").strip()
        prefixed = _apply_document_prefix(text, prefix)
        batch.append(ch)
        texts.append(prefixed)
        if len(batch) >= size:
            vectors = encoder.encode(texts, normalize_embeddings=True)
            for i, vec in enumerate(vectors):
                out = {**batch[i], "embedding": vec.tolist()}
                yield out
                total_yielded += 1
                if show_progress and total_yielded % (10 * size) == 0:
                    print(f"  embedded {total_yielded} chunks ...", flush=True)
            batch = []
            texts = []

    if batch:
        vectors = encoder.encode(texts, normalize_embeddings=True)
        for i, vec in enumerate(vectors):
            out = {**batch[i], "embedding": vec.tolist()}
            yield out
            total_yielded += 1
        if show_progress and total_yielded > 0:
            print(f"  embedded {total_yielded} chunks (done).", flush=True)


def embed_query(query: str) -> list[float]:
    """
    Embed a single query string for retrieval (e.g. search). Uses EMBED_QUERY_PREFIX from config.
    Returns 768-dim vector as list of floats.
    """
    from config import settings

    encoder = _get_encoder()
    prefixed = (settings.EMBED_QUERY_PREFIX + query) if query else query
    vector = encoder.encode([prefixed], normalize_embeddings=True)
    return vector[0].tolist()
