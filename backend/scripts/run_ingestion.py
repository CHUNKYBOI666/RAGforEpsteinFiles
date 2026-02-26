"""
Step 1: Run loader only. No chunking, embedding, or Qdrant.
Step 2 test: --chunk-test runs loader -> chunk_documents -> print samples.
Step 3A test: --embed-test runs loader -> chunk -> embed first 10 chunks (no Qdrant).
Step 3B test: --index-test runs load -> chunk -> embed -> index -> one semantic search.
Use --index-test --clear for trustworthy evaluation (wipes collection before indexing).

Sources: --source doc_explorer | biography | both (default: both).
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Iterator

# Project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qdrant_client import QdrantClient

from config import settings
from src.ingestion.chunking import chunk_documents
from src.ingestion.embedding import embed_chunks, embed_query
from src.ingestion.indexer import ensure_collection, upsert_chunks
from src.ingestion.cleaning import CLEANING_VERSION, clean_document
from src.ingestion.loaders import load_doc_explorer_documents


def _load_documents(source: str, max_docs: int | None) -> Iterator[dict]:
    """Yield documents from the given source. Used by all run_* functions."""
    if source == "doc_explorer":
        yield from load_doc_explorer_documents(settings.DOC_EXPLORER_DB_PATH, max_docs=max_docs)
    elif source == "biography":
        from src.ingestion.loaders import load_biography_documents
        yield from load_biography_documents(settings.BIOGRAPHY_DIR, max_docs=max_docs)
    elif source == "both":
        from itertools import chain
        from src.ingestion.loaders import load_biography_documents
        yield from chain(
            load_doc_explorer_documents(settings.DOC_EXPLORER_DB_PATH, max_docs=max_docs),
            load_biography_documents(settings.BIOGRAPHY_DIR, max_docs=max_docs),
        )
    else:
        raise ValueError(f"Unknown source: {source!r}")


def _maybe_clean(docs: Iterator[dict]) -> Iterator[dict]:
    """Wrap document iterator with cleaning when ENABLE_DOCUMENT_CLEANING is true."""
    if settings.ENABLE_DOCUMENT_CLEANING:
        for doc in docs:
            yield clean_document(doc)
    else:
        yield from docs


def _cleaning_version_arg() -> str | None:
    """Return the cleaning version tag when cleaning is enabled, else None."""
    return CLEANING_VERSION if settings.ENABLE_DOCUMENT_CLEANING else None


def run_loader_only(max_docs: int = 10, source: str = "both") -> None:
    """Original Step 1 behavior: load and print doc summary."""
    count = 0
    first = None
    for doc in _load_documents(source, max_docs):
        count += 1
        if first is None:
            first = doc
        if count <= 3:
            print(f"--- doc {count} ---")
            print(f"  doc_id: {doc['doc_id']}")
            ref = doc.get("source_ref", "")
            print(f"  source_ref: {ref[:80]}..." if len(ref) > 80 else f"  source_ref: {ref}")
            print(f"  doc_type: {doc['doc_type']}, doc_title: {doc['doc_title'][:50]}...")
            print(f"  text length: {len(doc['text'])} chars")
    print(f"\nTotal documents yielded: {count} (max_docs={max_docs}, source={source})")
    if first:
        print("\nFirst doc keys:", list(first.keys()))


def run_chunk_test(max_docs: int = 20, source: str = "both") -> None:
    """Step 2 test: load docs -> clean -> chunk -> print total count and sample chunks."""
    docs = _maybe_clean(_load_documents(source, max_docs))
    chunks = chunk_documents(docs, chunk_size=400, overlap=50, min_doc_chars=50, cleaning_version=_cleaning_version_arg())

    total = 0
    sample: list[dict] = []
    sample_cap = 3
    for ch in chunks:
        total += 1
        if len(sample) < sample_cap:
            sample.append(ch)

    print(f"Total chunks produced: {total} (from first {max_docs} docs)")
    print("\n--- Sample chunks (metadata structure) ---\n")
    for i, ch in enumerate(sample):
        # Pretty-print: full keys, truncated text, full metadata
        display = {k: v for k, v in ch.items()}
        if len(display.get("text", "")) > 200:
            display["text"] = display["text"][:200] + "..."
        print(f"Chunk {i + 1}:")
        print(json.dumps(display, indent=2, default=str))
        print()

def run_embed_test(max_chunks: int = 10, source: str = "both") -> None:
    """Step 3A: load -> clean -> chunk -> embed first N chunks; print shape and sample (no Qdrant)."""
    docs = _maybe_clean(_load_documents(source, 50))
    chunks = chunk_documents(docs, chunk_size=400, overlap=50, min_doc_chars=50, cleaning_version=_cleaning_version_arg())
    # Consume until we have max_chunks
    chunk_list: list[dict] = []
    for ch in chunks:
        chunk_list.append(ch)
        if len(chunk_list) >= max_chunks:
            break
    if not chunk_list:
        print("No chunks produced. Try increasing max_docs or relaxing min_doc_chars.")
        return
    embedded = embed_chunks(chunk_list, batch_size=min(10, len(chunk_list)))
    results = list(embedded)
    print(f"Embedded {len(results)} chunks (requested up to {max_chunks}).")
    if results:
        first = results[0]
        vec = first.get("embedding", [])
        print(f"First chunk_id: {first.get('chunk_id')}")
        print(f"Embedding dim: {len(vec)}")
        print(f"First 5 values: {vec[:5]}")
        print("Keys on embedded chunk:", list(first.keys()))


def run_index_test(
    max_docs: int = 50,
    query_text: str = "flight log",
    top_k: int = 3,
    source: str = "both",
    clear_first: bool = False,
) -> None:
    """Step 3B: load -> chunk -> embed -> ensure collection -> upsert -> one semantic search, print hits."""
    settings.QDRANT_PATH.mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=str(settings.QDRANT_PATH))
    collection_name = settings.QDRANT_COLLECTION

    if clear_first and client.collection_exists(collection_name):
        client.delete_collection(collection_name)
        print(f"Cleared collection {collection_name!r}.", flush=True)

    docs = _maybe_clean(_load_documents(source, max_docs))
    alnum_dropped: list[int] = [0]
    chunks = chunk_documents(
        docs,
        chunk_size=400,
        overlap=50,
        min_doc_chars=50,
        cleaning_version=_cleaning_version_arg(),
        min_alnum_ratio=0.5,
        alnum_dropped=alnum_dropped,
    )
    # show_progress so full runs print periodic status (embed + upsert are slow at scale)
    embedded = embed_chunks(chunks, batch_size=min(32, 64), show_progress=True)

    ensure_collection(client, collection_name, vector_size=768)
    print("Embedding + indexing (progress below)...", flush=True)
    count = upsert_chunks(client, collection_name, embedded, show_progress=True)
    print(f"Upserted {count} chunks into {collection_name!r}.")
    if alnum_dropped[0] > 0:
        print(f"Dropped {alnum_dropped[0]} chunks (alnum < 50%).", flush=True)

    query_vector = embed_query(query_text)
    response = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        limit=top_k,
    )
    hits = response.points

    print(f"\nTop {top_k} hits for query {query_text!r}:")
    for i, hit in enumerate(hits, 1):
        payload = hit.payload or {}
        text = (payload.get("text") or "")[:200]
        if len(payload.get("text") or "") > 200:
            text += "..."
        print(f"  {i}. chunk_id={payload.get('chunk_id')} doc_id={payload.get('doc_id')} doc_type={payload.get('doc_type')} doc_date={payload.get('doc_date')} score={hit.score:.4f}")
        print(f"     {text}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ingestion: loader only or chunk test")
    parser.add_argument(
        "--chunk-test",
        action="store_true",
        help="Run chunking on first 20 docs and print sample chunks (Step 2 test)",
    )
    parser.add_argument(
        "--embed-test",
        action="store_true",
        help="Step 3A: embed first 10 chunks (no Qdrant)",
    )
    parser.add_argument(
        "--index-test",
        action="store_true",
        help="Step 3B: load -> chunk -> embed -> index -> one semantic search",
    )
    parser.add_argument(
        "--max-docs",
        type=int,
        default=None,
        help="Max docs to load (default: 10 for loader, 20 for --chunk-test)",
    )
    parser.add_argument(
        "--source",
        type=str,
        choices=("doc_explorer", "biography", "both"),
        default="both",
        help="Data source: both (default), doc_explorer, or biography",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="No doc limit: load/index entire corpus (use with --index-test for full pipeline)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Wipe the Qdrant collection before indexing so re-runs are from a clean state (use with --index-test)",
    )
    args = parser.parse_args()

    max_docs = None if args.full else args.max_docs

    if args.index_test:
        if max_docs is None and not args.full:
            max_docs = 50
        run_index_test(max_docs=max_docs, source=args.source, clear_first=args.clear)
    elif args.embed_test:
        run_embed_test(max_chunks=10, source=args.source)
    elif args.chunk_test:
        max_docs = max_docs if max_docs is not None else 20
        run_chunk_test(max_docs=max_docs, source=args.source)
    else:
        # Loader only: default 10 for quick check; --source both with no limit → full corpus
        if max_docs is None:
            max_docs = 10 if args.source != "both" else None
        run_loader_only(max_docs=max_docs, source=args.source)


if __name__ == "__main__":
    main()
