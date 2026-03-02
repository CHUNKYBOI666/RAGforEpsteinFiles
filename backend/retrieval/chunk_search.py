"""Stage 3: fine chunk-level search against embedding restricted to candidate doc_ids; returns top chunks."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Dict, List, Sequence

from supabase import Client, create_client

# Load backend/.env then backend/config.py so credentials work from any cwd
_backend_dir = Path(__file__).resolve().parent.parent
_dotenv_path = _backend_dir / ".env"
if _dotenv_path.exists():
    from dotenv import load_dotenv

    load_dotenv(_dotenv_path, override=True)

_config_py = _backend_dir / "config.py"
_spec = importlib.util.spec_from_file_location("_env_config", _config_py)
_env_config = importlib.util.module_from_spec(_spec)
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(_env_config)

SUPABASE_URL: str = getattr(_env_config, "SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY: str = getattr(_env_config, "SUPABASE_SERVICE_ROLE_KEY", "")

CHUNK_EMBED_DIM = 1536
CHUNK_MATCH_FN = "match_chunks_in_docs"


def _validate_config() -> None:
    missing = []
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_SERVICE_ROLE_KEY:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")
    if missing:
        joined = ", ".join(missing)
        raise SystemExit(
            f"Missing required configuration values: {joined}. "
            "Set them in backend/.env or your environment."
        )


def _create_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def _coerce_embedding(vec: Sequence[float]) -> List[float]:
    """Convert an arbitrary sequence to a list[float] and validate length."""
    if not vec:
        return []
    try:
        result = [float(x) for x in vec]
    except (TypeError, ValueError) as exc:  # noqa: BLE001
        raise ValueError("query_embedding must be a sequence of numbers") from exc

    if len(result) != CHUNK_EMBED_DIM:
        raise ValueError(
            f"query_embedding must have length {CHUNK_EMBED_DIM}, "
            f"got {len(result)}"
        )
    return result


def _clean_doc_ids(doc_ids: Sequence[str]) -> List[str]:
    clean: List[str] = []
    seen = set()
    for raw in doc_ids:
        if raw is None:
            continue
        s = str(raw).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        clean.append(s)
    return clean


def chunk_search(
    query_embedding: Sequence[float],
    candidate_doc_ids: Sequence[str],
    top_k: int = 5,
) -> List[Dict[str, object]]:
    """Search chunks.embedding within candidate docs and return top chunks.

    Returns a list of dicts with keys:
      - doc_id: str
      - chunk_index: int
      - chunk_text: str
      - similarity: float
    """
    _validate_config()

    if top_k <= 0:
        raise ValueError("top_k must be a positive integer")

    embedding = _coerce_embedding(query_embedding)
    if not embedding:
        return []

    clean_doc_ids = _clean_doc_ids(candidate_doc_ids)
    if not clean_doc_ids:
        return []

    client = _create_supabase_client()

    try:
        resp = client.rpc(
            CHUNK_MATCH_FN,
            {
                "query_embedding": embedding,
                "doc_ids": clean_doc_ids,
                "match_count": top_k,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"Failed to execute RPC {CHUNK_MATCH_FN!r} against Supabase"
        ) from exc

    rows = resp.data or []
    if not rows:
        return []

    results: List[Dict[str, object]] = []
    for row in rows:
        doc_id = row.get("doc_id")
        chunk_index = row.get("chunk_index")
        chunk_text = row.get("chunk_text")
        similarity = row.get("similarity")
        if doc_id is None or chunk_index is None or chunk_text is None:
            continue
        results.append(
            {
                "doc_id": doc_id,
                "chunk_index": int(chunk_index),
                "chunk_text": str(chunk_text),
                "similarity": float(similarity) if similarity is not None else 0.0,
            }
        )
        if len(results) >= top_k:
            break

    return results


def _load_embedding_from_file(path: Path) -> List[float]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Embedding file must contain a JSON list of numbers")
    return _coerce_embedding(data)


def _load_doc_ids_from_file(path: Path) -> List[str]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Doc IDs file must contain a JSON list of strings")
    return _clean_doc_ids(data)


def _make_dummy_embedding() -> List[float]:
    return [0.0] * CHUNK_EMBED_DIM


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Stage 3: run chunk-level vector search against chunks.embedding "
            "restricted to candidate doc_ids via match_chunks_in_docs RPC."
        )
    )
    parser.add_argument(
        "-k",
        "--top-k",
        type=int,
        default=5,
        help="Number of chunks to return (default: 5).",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--embedding-file",
        type=str,
        help=(
            "Path to JSON file containing a list of floats "
            f"for the query embedding (expected length {CHUNK_EMBED_DIM})."
        ),
    )
    group.add_argument(
        "--dummy",
        action="store_true",
        help=(
            "Use a dummy all-zero embedding (length "
            f"{CHUNK_EMBED_DIM}) just to exercise the pipeline."
        ),
    )
    parser.add_argument(
        "--doc-ids-file",
        type=str,
        required=True,
        help="Path to JSON file containing a list of candidate doc_id strings.",
    )

    args = parser.parse_args()

    doc_ids_path = Path(args.doc_ids_file)
    candidate_doc_ids = _load_doc_ids_from_file(doc_ids_path)

    if not candidate_doc_ids:
        raise SystemExit("No candidate doc_ids loaded from --doc-ids-file.")

    if args.embedding_file is not None:
        embedding = _load_embedding_from_file(Path(args.embedding_file))
    elif args.dummy:
        embedding = _make_dummy_embedding()
    else:
        raise SystemExit(
            "You must provide either --embedding-file PATH or --dummy "
            "to build a query embedding for testing."
        )

    chunks = chunk_search(embedding, candidate_doc_ids, top_k=args.top_k)

    if not chunks:
        print("No matching chunks found.")
    else:
        print("Top chunks:")
        for idx, ch in enumerate(chunks, start=1):
            text_preview = ch["chunk_text"]
            if isinstance(text_preview, str) and len(text_preview) > 200:
                text_preview = text_preview[:200] + "..."
            print(
                f"{idx}. DOC_ID={ch['doc_id']}, index={ch['chunk_index']}, "
                f"similarity={ch['similarity']:.4f}"
            )
            print(f"   TEXT: {text_preview}")

