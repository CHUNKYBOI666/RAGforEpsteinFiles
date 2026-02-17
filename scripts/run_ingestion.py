"""
Step 1: Run HF loader only. No chunking, embedding, or Qdrant.
Step 2 test: --chunk-test runs loader (20 docs) -> chunk_documents -> print samples.
Use this to verify the loader and dataset shape before building the rest of the pipeline.
"""
import argparse
import json
import sys
from pathlib import Path

# Project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ingestion.chunking import chunk_documents
from src.ingestion.loaders import load_hf_documents


def run_loader_only(max_docs: int = 10) -> None:
    """Original Step 1 behavior: load and print doc summary."""
    count = 0
    first = None
    for doc in load_hf_documents(max_docs=max_docs):
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
    print(f"\nTotal documents yielded: {count} (max_docs={max_docs})")
    if first:
        print("\nFirst doc keys:", list(first.keys()))


def run_chunk_test(max_docs: int = 20) -> None:
    """Step 2 test: load docs -> chunk -> print total count and sample chunks."""
    docs = load_hf_documents(max_docs=max_docs)
    chunks = chunk_documents(docs, chunk_size=700, overlap=100, min_doc_chars=50)

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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ingestion: loader only or chunk test")
    parser.add_argument(
        "--chunk-test",
        action="store_true",
        help="Run chunking on first 20 docs and print sample chunks (Step 2 test)",
    )
    parser.add_argument(
        "--max-docs",
        type=int,
        default=None,
        help="Max docs to load (default: 10 for loader, 20 for --chunk-test)",
    )
    args = parser.parse_args()

    if args.chunk_test:
        max_docs = args.max_docs if args.max_docs is not None else 20
        run_chunk_test(max_docs=max_docs)
    else:
        max_docs = args.max_docs if args.max_docs is not None else 10
        run_loader_only(max_docs=max_docs)


if __name__ == "__main__":
    main()
