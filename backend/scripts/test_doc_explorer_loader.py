"""Standalone test for load_doc_explorer_documents. Run from backend: python scripts/test_doc_explorer_loader.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import DOC_EXPLORER_DB_PATH
from src.ingestion.loaders import load_doc_explorer_documents


def main() -> None:
    print("Testing load_doc_explorer_documents with max_docs=5")
    print("DB path:", DOC_EXPLORER_DB_PATH)
    print()
    for i, doc in enumerate(load_doc_explorer_documents(DOC_EXPLORER_DB_PATH, max_docs=5)):
        print(f"--- doc {i + 1} ---")
        print("  keys:", list(doc.keys()))
        print("  doc_id:", doc["doc_id"][:60] + "..." if len(doc["doc_id"]) > 60 else doc["doc_id"])
        print("  doc_type:", doc["doc_type"])
        print("  doc_date:", doc["doc_date"])
        print("  doc_title:", (doc["doc_title"] or "")[:60] + "..." if len(doc.get("doc_title") or "") > 60 else doc.get("doc_title"))
        text = doc.get("text") or ""
        print("  text sample:", text[:200] + "..." if len(text) > 200 else text[:200])
        print()
    print("Standalone test OK: doc_type and doc_date present.")


if __name__ == "__main__":
    main()
