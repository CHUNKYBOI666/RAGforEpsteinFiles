# /api/graph endpoint: entity-relationship graph from rdf_triples (nodes = actors/targets, edges = triples).

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict, List, Optional

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


DEFAULT_LIMIT = 500


def _apply_date_keyword_filters(query, date_from: Optional[str], date_to: Optional[str], keywords: Optional[str]):
    if date_from and date_from.strip():
        query = query.gte("timestamp", date_from.strip())
    if date_to and date_to.strip():
        query = query.lte("timestamp", date_to.strip())
    if keywords and keywords.strip():
        parts = [p.strip() for p in keywords.split(",") if p.strip()]
        if parts:
            or_parts = []
            for p in parts:
                pattern = f"%{p}%"
                or_parts.append(f"action.ilike.{pattern}")
                or_parts.append(f"location.ilike.{pattern}")
            query = query.or_(",".join(or_parts))
    return query


def _fetch_triples_centered_on_entity(
    client: Client,
    name: str,
    date_from: Optional[str],
    date_to: Optional[str],
    keywords: Optional[str],
    limit: int,
) -> List[Dict[str, Any]]:
    """Fetch triples where actor=name or target=name; merge and dedupe."""
    seen_keys: set = set()
    out: List[Dict[str, Any]] = []
    for col in ("actor", "target"):
        query = (
            client.table("rdf_triples")
            .select("actor, action, target, timestamp, location, doc_id")
            .eq(col, name)
        )
        query = _apply_date_keyword_filters(query, date_from, date_to, keywords)
        query = query.limit(limit * 2)
        try:
            resp = query.execute()
        except Exception as exc:
            raise RuntimeError("Failed to query rdf_triples for graph from Supabase") from exc
        for r in (resp.data or []):
            key = (r.get("actor"), r.get("action"), r.get("target"), r.get("doc_id"))
            if key not in seen_keys:
                seen_keys.add(key)
                out.append(r)
            if len(out) >= limit:
                return out
    return out


def _fetch_triples_no_entity(
    client: Client,
    date_from: Optional[str],
    date_to: Optional[str],
    keywords: Optional[str],
    limit: int,
) -> List[Dict[str, Any]]:
    """Fetch triples with optional date/keyword filters, no entity filter."""
    query = (
        client.table("rdf_triples")
        .select("actor, action, target, timestamp, location, doc_id")
    )
    query = _apply_date_keyword_filters(query, date_from, date_to, keywords)
    query = query.limit(limit)
    try:
        resp = query.execute()
    except Exception as exc:
        raise RuntimeError("Failed to query rdf_triples for graph from Supabase") from exc
    return resp.data or []


def get_graph(
    entity: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    keywords: Optional[str] = None,
    limit: int = DEFAULT_LIMIT,
) -> Dict[str, Any]:
    """Query rdf_triples with optional filters; return nodes (entities) and edges (triples)."""
    limit = max(1, min(limit, 2000))
    client = _create_supabase_client()

    if entity and entity.strip():
        name = entity.strip()
        rows = _fetch_triples_centered_on_entity(client, name, date_from, date_to, keywords, limit)
    else:
        rows = _fetch_triples_no_entity(client, date_from, date_to, keywords, limit)
    node_counts: Dict[str, int] = {}
    edges: List[Dict[str, Any]] = []

    for r in rows:
        actor = (r.get("actor") or "").strip()
        target = (r.get("target") or "").strip()
        action = (r.get("action") or "").strip()
        timestamp = r.get("timestamp") or ""
        location = r.get("location") or ""
        doc_id = r.get("doc_id") or ""

        if actor:
            node_counts[actor] = node_counts.get(actor, 0) + 1
        if target:
            node_counts[target] = node_counts.get(target, 0) + 1
        if actor or target:
            edges.append({
                "source": actor or "(unknown)",
                "target": target or "(unknown)",
                "action": action,
                "doc_id": doc_id,
                "timestamp": timestamp,
                "location": location,
            })

    nodes = [
        {"id": nid, "label": nid, "count": node_counts[nid]}
        for nid in sorted(node_counts.keys())
    ]

    return {"nodes": nodes, "edges": edges}


router = APIRouter(tags=["graph"])


@router.get("/graph")
def api_graph(
    entity: Optional[str] = Query(None, description="Center graph on entity (actor/target match)"),
    date_from: Optional[str] = Query(None, description="Filter triples with timestamp >= date_from"),
    date_to: Optional[str] = Query(None, description="Filter triples with timestamp <= date_to"),
    keywords: Optional[str] = Query(None, description="Comma-separated keywords; filter action/location (fuzzy)"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=2000, description="Max number of triples to return"),
):
    """GET /api/graph — nodes (entities) and edges (triples) for relationship graph visualization."""
    return get_graph(entity=entity, date_from=date_from, date_to=date_to, keywords=keywords, limit=limit)
