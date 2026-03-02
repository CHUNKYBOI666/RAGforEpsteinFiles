# /api/search endpoint: fuzzy search for actor/entity names; returns canonical names and relationship counts.

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Query
from supabase import Client, create_client

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


def _create_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def search_entities(query: str) -> List[Dict[str, Any]]:
    """Fuzzy search entity_aliases; return distinct canonical_name with relationship count from rdf_triples."""
    q = (query or "").strip()
    if not q:
        return []
    client = _create_supabase_client()
    pattern = f"%{q}%"
    try:
        # Match original_name or canonical_name
        resp = (
            client.table("entity_aliases")
            .select("canonical_name")
            .or_(f"original_name.ilike.{pattern},canonical_name.ilike.{pattern}")
            .limit(100)
            .execute()
        )
    except Exception as exc:
        raise RuntimeError("Failed to query entity_aliases from Supabase") from exc
    rows = resp.data or []
    canonical_names = list({r.get("canonical_name") for r in rows if r.get("canonical_name")})
    if not canonical_names:
        return []

    # Count triples where actor or target equals each canonical name (head=True for count only)
    out: List[Dict[str, Any]] = []
    for name in canonical_names:
        try:
            r_actor = (
                client.table("rdf_triples")
                .select("*", count="exact", head=True)
                .eq("actor", name)
                .execute()
            )
            r_target = (
                client.table("rdf_triples")
                .select("*", count="exact", head=True)
                .eq("target", name)
                .execute()
            )
        except Exception as exc:
            raise RuntimeError("Failed to count rdf_triples from Supabase") from exc
        count_actor = getattr(r_actor, "count", None) or 0
        count_target = getattr(r_target, "count", None) or 0
        # Relationship count: triples where this entity is actor or target (may double-count same triple)
        count = count_actor + count_target
        out.append({"canonical_name": name, "count": count})
    out.sort(key=lambda x: -x["count"])
    return out


router = APIRouter(tags=["search"])


@router.get("/search")
def api_search(q: str = Query(..., description="Search for actor/entity name")):
    """GET /api/search?q= — fuzzy search for canonical entity names and relationship counts."""
    return search_entities(q)
