"""Triple-based candidate doc_id search: find doc_ids from rdf_triples by actor/target/action terms."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from typing import List, Sequence

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

# RPC name in Supabase (must run ingestion/rpc_triple_candidate_doc_ids.sql first).
_GET_DOC_IDS_RPC = "get_doc_ids_by_triple_terms"
# Max terms to pass to RPC (avoids huge arrays).
_MAX_TERMS = 50


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


def _clean_terms(search_terms: Sequence[str]) -> List[str]:
    clean: List[str] = []
    seen_lower = set()
    for raw in search_terms:
        if raw is None:
            continue
        s = str(raw).strip()
        if not s:
            continue
        key = s.lower()
        if key in seen_lower:
            continue
        seen_lower.add(key)
        clean.append(s)
    return clean


def get_doc_ids_by_triple_terms(
    search_terms: Sequence[str],
    top_k: int = 25,
) -> List[str]:
    """Return doc_ids that have at least one triple matching any term in actor/target/action.

    Used to expand candidate doc_ids (with summary search) so entity+keyword-relevant
    documents surface even when summary embedding similarity is low.
    """
    _validate_config()

    clean_terms = _clean_terms(search_terms)
    if not clean_terms or top_k <= 0:
        return []

    # Prefer short terms for better substring match; cap to avoid huge RPC payload.
    terms_for_query = sorted(clean_terms, key=len)[:_MAX_TERMS]

    client = _create_supabase_client()

    try:
        resp = client.rpc(
            _GET_DOC_IDS_RPC,
            {"search_terms": terms_for_query, "max_doc_ids": top_k},
        ).execute()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"Failed to run {_GET_DOC_IDS_RPC!r} on Supabase. "
            "Ensure ingestion/rpc_triple_candidate_doc_ids.sql has been applied."
        ) from exc

    rows = resp.data or []
    doc_ids: List[str] = []
    for row in rows:
        doc_id = row.get("doc_id")
        if doc_id is not None:
            s = str(doc_id).strip()
            if s:
                doc_ids.append(s)

    return doc_ids


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Get doc_ids from rdf_triples where actor/target/action match any search term."
        )
    )
    parser.add_argument(
        "-k",
        "--top-k",
        type=int,
        default=25,
        help="Max number of distinct doc_ids to return (default 25).",
    )
    parser.add_argument(
        "--term",
        dest="terms",
        action="append",
        help="Search term (can be passed multiple times).",
    )

    args = parser.parse_args()
    terms = args.terms or []

    if not terms:
        raise SystemExit("At least one --term is required.")

    doc_ids = get_doc_ids_by_triple_terms(terms, top_k=args.top_k)

    if not doc_ids:
        print("No matching doc_ids found.")
    else:
        print("Doc IDs from triples:")
        for idx, doc_id in enumerate(doc_ids, start=1):
            print(f"{idx}. {doc_id}")
