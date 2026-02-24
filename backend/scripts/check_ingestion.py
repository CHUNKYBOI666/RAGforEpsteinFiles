"""
Verify that the dataset is ingested into Qdrant: collection exists, vector config, point count.
Run from backend/ with: PYTHONPATH=. .venv/bin/python scripts/check_ingestion.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qdrant_client import QdrantClient

from config import settings


def main() -> None:
    path = settings.QDRANT_PATH
    collection_name = settings.QDRANT_COLLECTION

    if not path.exists():
        print(f"Qdrant path does not exist: {path}")
        print("Ingestion has not been run. Run: python scripts/run_ingestion.py --index-test [--max-docs N]")
        return

    client = QdrantClient(path=str(path))

    if not client.collection_exists(collection_name):
        print(f"Collection {collection_name!r} does not exist at {path}.")
        print("Ingestion has not been run. Run: python scripts/run_ingestion.py --index-test [--max-docs N]")
        return

    info = client.get_collection(collection_name)
    vectors_config = info.config.params.vectors
    vector_size = getattr(vectors_config, "size", None) if hasattr(vectors_config, "size") else None
    if vector_size is None and hasattr(vectors_config, "items"):
        first = next(iter(vectors_config.values()), None)
        vector_size = getattr(first, "size", None) if first else None

    result = client.count(collection_name)
    count = result.count if hasattr(result, "count") else result

    print(f"Collection: {collection_name!r}")
    print(f"Path: {path}")
    print(f"Vector size: {vector_size}")
    print(f"Point count: {count}")

    if count == 0:
        print("\nIndex is empty. Run: python scripts/run_ingestion.py --index-test [--max-docs N]")
    else:
        print("\nIngestion verified. Retrieval and chat can use this index.")


if __name__ == "__main__":
    main()
