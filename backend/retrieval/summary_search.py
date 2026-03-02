"""Stage 2: coarse document-level search against summary_embedding; returns top candidate doc_ids."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import List, Sequence, Set

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

SUMMARY_EMBED_DIM = 1536
SUMMARY_MATCH_FN = "match_chunks_summary"


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

    if len(result) != SUMMARY_EMBED_DIM:
        raise ValueError(
            f"query_embedding must have length {SUMMARY_EMBED_DIM}, "
            f"got {len(result)}"
        )
    return result


def summary_search(query_embedding: Sequence[float], top_k: int = 20) -> List[str]:
    """Search chunks.summary_embedding via Supabase RPC and return distinct doc_ids.

    The RPC function `match_chunks_summary` must exist in the database with signature:

        match_chunks_summary(query_embedding vector(1536), match_count int DEFAULT 20)

    and return rows containing at least: doc_id (text), similarity (float).
    """
    _validate_config()

    if top_k <= 0:
        raise ValueError("top_k must be a positive integer")

    embedding = _coerce_embedding(query_embedding)
    if not embedding:
        return []

    client = _create_supabase_client()

    try:
        resp = client.rpc(
            SUMMARY_MATCH_FN,
            {"query_embedding": embedding, "match_count": top_k},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"Failed to execute RPC {SUMMARY_MATCH_FN!r} against Supabase"
        ) from exc

    rows = resp.data or []
    seen: Set[str] = set()
    doc_ids: List[str] = []

    for row in rows:
        doc_id = row.get("doc_id")
        if not doc_id or doc_id in seen:
            continue
        seen.add(doc_id)
        doc_ids.append(doc_id)
        if len(doc_ids) >= top_k:
            break

    return doc_ids


def _load_embedding_from_file(path: Path) -> List[float]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Embedding file must contain a JSON list of numbers")
    return _coerce_embedding(data)


def _make_dummy_embedding() -> List[float]:
    return [0.0] * SUMMARY_EMBED_DIM


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Stage 2: run summary-level vector search against "
            "chunks.summary_embedding via match_chunks_summary RPC."
        )
    )
    parser.add_argument(
        "-k",
        "--top-k",
        type=int,
        default=20,
        help="Number of distinct doc_ids to return (default: 20).",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--from-file",
        type=str,
        help=(
            "Path to JSON file containing a list of floats "
            f"for the query embedding (expected length {SUMMARY_EMBED_DIM})."
        ),
    )
    group.add_argument(
        "--dummy",
        action="store_true",
        help=(
            "Use a dummy all-zero embedding (length "
            f"{SUMMARY_EMBED_DIM}) just to exercise the pipeline."
        ),
    )

    args = parser.parse_args()

    if args.from_file:
        embedding = _load_embedding_from_file(Path(args.from_file))
    elif args.dummy:
        embedding = _make_dummy_embedding()
    else:
        raise SystemExit(
            "You must provide either --from-file PATH or --dummy to build a query "
            "embedding for testing."
        )

    results = summary_search(embedding, top_k=args.top_k)

    if not results:
        print("No matching documents found.")
    else:
        print("Top doc_ids:")
        for idx, doc_id in enumerate(results, start=1):
            print(f"{idx}. {doc_id}")

