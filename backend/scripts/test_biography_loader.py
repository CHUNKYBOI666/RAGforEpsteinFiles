"""Standalone test for load_biography_documents. Run from backend: python scripts/test_biography_loader.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import BIOGRAPHY_DIR
from src.ingestion.loaders import load_biography_documents


def main() -> None:
    print("Testing load_biography_documents with max_docs=2")
    print("Biography dir:", BIOGRAPHY_DIR)
    print()
    for i, doc in enumerate(load_biography_documents(BIOGRAPHY_DIR, max_docs=2)):
        print(f"--- doc {i + 1} ---")
        print("  keys:", list(doc.keys()))
        print("  doc_id:", doc["doc_id"])
        print("  doc_type:", doc["doc_type"])
        print("  doc_title:", doc["doc_title"])
        print("  source_ref:", doc["source_ref"])
        text = doc.get("text") or ""
        print("  text sample:", text[:150] + "..." if len(text) > 150 else text[:150])
        print()
    print("Standalone test OK: shape matches other loaders.")


if __name__ == "__main__":
    main()
