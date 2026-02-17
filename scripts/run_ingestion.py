"""
Step 1: Run HF loader only. No chunking, embedding, or Qdrant.
Use this to verify the loader and dataset shape before building the rest of the pipeline.
"""
import sys
from pathlib import Path

# Project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ingestion.loaders import load_hf_documents


def main() -> None:
    # Limit for quick review; remove max_docs for full run
    max_docs = 10
    count = 0
    first = None
    for doc in load_hf_documents(max_docs=max_docs):
        count += 1
        if first is None:
            first = doc
        if count <= 3:
            print(f"--- doc {count} ---")
            print(f"  doc_id: {doc['doc_id']}")
            print(f"  source_ref: {doc['source_ref'][:80]}..." if len(doc.get("source_ref", "")) > 80 else f"  source_ref: {doc['source_ref']}")
            print(f"  doc_type: {doc['doc_type']}, doc_title: {doc['doc_title'][:50]}...")
            print(f"  text length: {len(doc['text'])} chars")
    print(f"\nTotal documents yielded: {count} (max_docs={max_docs})")
    if first:
        print("\nFirst doc keys:", list(first.keys()))


if __name__ == "__main__":
    main()
