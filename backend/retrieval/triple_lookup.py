"""Stage 4: structured fact retrieval from rdf_triples for given doc_ids, filtered by expanded query terms."""

from __future__ import annotations

import argparse
import importlib.util
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

# Cap terms so the PostgREST .or_() filter does not exceed URL/parser limits.
MAX_TRIPLE_LOOKUP_TERMS = 40


def _escape_for_postgrest_quoted(s: str) -> str:
    """Escape string for use inside double-quoted value in PostgREST filter (\\ and \")."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


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


def triple_lookup(doc_ids: List[str], search_terms: List[str]) -> List[Dict[str, str]]:
    """Fetch rdf_triples for doc_ids where actor or target matches any search term."""
    _validate_config()

    clean_doc_ids = _clean_doc_ids(doc_ids)
    clean_terms = _clean_terms(search_terms)[:MAX_TRIPLE_LOOKUP_TERMS]

    if not clean_doc_ids or not clean_terms:
        return []

    client = _create_supabase_client()

    # Build OR filter with quoted patterns so PostgREST parses % and special chars as string value.
    filters: List[str] = []
    for term in clean_terms:
        pattern = f"%{term}%"
        escaped = _escape_for_postgrest_quoted(pattern)
        filters.append(f'actor.ilike."{escaped}"')
        filters.append(f'target.ilike."{escaped}"')
    or_filter = ",".join(filters)

    try:
        query = (
            client.table("rdf_triples")
            .select("actor, action, target, timestamp, location, doc_id")
            .in_("doc_id", clean_doc_ids)
            .or_(or_filter)
            .limit(500)
        )
        resp = query.execute()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Failed to query rdf_triples from Supabase") from exc

    rows = resp.data or []
    if not rows:
        return []

    results: List[Dict[str, str]] = []
    for row in rows:
        doc_id = row.get("doc_id")
        if not doc_id:
            continue
        results.append(
            {
                "actor": row.get("actor") or "",
                "action": row.get("action") or "",
                "target": row.get("target") or "",
                "timestamp": row.get("timestamp") or "",
                "location": row.get("location") or "",
                "doc_id": str(doc_id),
            }
        )

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Stage 4: fetch rdf_triples for candidate doc_ids where actor or "
            "target matches any of the provided search terms."
        )
    )
    parser.add_argument(
        "--doc-id",
        dest="doc_ids",
        action="append",
        help="Document ID to include (can be passed multiple times).",
    )
    parser.add_argument(
        "--term",
        dest="terms",
        action="append",
        help="Search term to match against actor/target (can be passed multiple times).",
    )

    args = parser.parse_args()

    doc_ids = args.doc_ids or []
    terms = args.terms or []

    if not doc_ids:
        raise SystemExit("At least one --doc-id is required.")
    if not terms:
        raise SystemExit("At least one --term is required.")

    triples = triple_lookup(doc_ids, terms)

    if not triples:
        print("No matching triples found.")
    else:
        print("Triples:")
        for idx, t in enumerate(triples, start=1):
            print(
                f"{idx}. [DOC_ID={t['doc_id']}] "
                f"ACTOR={t['actor']!r}, ACTION={t['action']!r}, "
                f"TARGET={t['target']!r}, TIME={t['timestamp']!r}, "
                f"LOC={t['location']!r}"
            )

