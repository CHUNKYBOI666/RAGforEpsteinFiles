# /api/stats and /api/tag-clusters: database stats (doc/triple/chunk/actor counts) and tag clusters proxy.

from __future__ import annotations

import importlib.util
import json
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter
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
SUPABASE_DB_URL: str = getattr(_env_config, "SUPABASE_DB_URL", "") or ""

_log = logging.getLogger(__name__)


def _create_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def get_stats() -> Dict[str, int]:
    """Return document count, triple count, chunk count, distinct actor count."""
    client = _create_supabase_client()
    try:
        # Use limit(1) instead of head=True: HEAD+count can yield empty bodies that break
        # postgrest-py JSON parsing (and some proxies return non-JSON errors for HEAD).
        r_docs = (
            client.table("documents")
            .select("doc_id", count="exact")
            .limit(1)
            .execute()
        )
        r_triples = (
            client.table("rdf_triples")
            .select("id", count="exact")
            .limit(1)
            .execute()
        )
        r_chunks = (
            client.table("chunks")
            .select("id", count="exact")
            .limit(1)
            .execute()
        )
    except Exception as exc:
        raise RuntimeError("Failed to query counts from Supabase") from exc
    doc_count = getattr(r_docs, "count", None) or 0
    triple_count = getattr(r_triples, "count", None) or 0
    chunk_count = getattr(r_chunks, "count", None) or 0
    # Distinct actors: must be one SQL round-trip (RPC or direct Postgres). Paginating `actor` via REST
    # issues one API call per 1k rows and burns Supabase quota fast in production.
    actor_count = _get_distinct_actor_count(client)
    return {
        "document_count": doc_count,
        "triple_count": triple_count,
        "chunk_count": chunk_count,
        "actor_count": actor_count,
    }


def _rpc_scalar_to_int(raw: Any) -> int | None:
    """Normalize PostgREST RPC payload for a single bigint/scalar."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, (int, float)):
        return int(raw)
    if isinstance(raw, str) and raw.strip().lstrip("-").isdigit():
        return int(raw.strip())
    if isinstance(raw, list) and len(raw) > 0:
        return _rpc_scalar_to_int(raw[0])
    if isinstance(raw, dict):
        for k in ("count", "count_distinct_rdf_actors", "result"):
            if k in raw and raw[k] is not None:
                return _rpc_scalar_to_int(raw[k])
    return None


def _get_distinct_actor_count(client: Client) -> int:
    """Count distinct non-null, non-empty `actor` in rdf_triples (single query)."""
    try:
        resp = client.rpc("count_distinct_rdf_actors").execute()
        n = _rpc_scalar_to_int(resp.data)
        if n is not None:
            return max(0, n)
    except Exception as exc:
        _log.warning("count_distinct_rdf_actors RPC failed: %s", exc)

    db_url = SUPABASE_DB_URL.strip()
    if db_url:
        try:
            import psycopg

            with psycopg.connect(db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT COUNT(DISTINCT TRIM(actor))::bigint
                        FROM rdf_triples
                        WHERE actor IS NOT NULL AND TRIM(actor) <> ''
                        """
                    )
                    row = cur.fetchone()
                    if row and row[0] is not None:
                        return int(row[0])
        except Exception as exc:
            _log.warning("distinct actor count via SUPABASE_DB_URL failed: %s", exc)

    _log.warning(
        "actor_count unavailable: run backend/ingestion/rpc_count_distinct_rdf_actors.sql in Supabase "
        "or set SUPABASE_DB_URL; returning 0"
    )
    return 0


def _parse_cluster_ids(raw: Any) -> List[str]:
    """Parse top_cluster_ids (TEXT): try JSON array, else comma-separated, else single value."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if x is not None and str(x).strip()]
    s = str(raw).strip()
    if not s:
        return []
    if s.startswith("["):
        try:
            arr = json.loads(s)
            return [str(x).strip() for x in arr if x is not None and str(x).strip()]
        except json.JSONDecodeError:
            pass
    return [x.strip() for x in re.split(r"[,;]", s) if x.strip()]


def get_tag_clusters(limit: int = 30) -> List[Dict[str, Any]]:
    """Return up to `limit` semantic tag clusters from rdf_triples.top_cluster_ids."""
    client = _create_supabase_client()
    counter: Counter[str] = Counter()
    page_size = 2000
    offset = 0
    for _ in range(50):
        try:
            resp = (
                client.table("rdf_triples")
                .select("top_cluster_ids")
                .not_.is_("top_cluster_ids", "null")
                .range(offset, offset + page_size - 1)
                .execute()
            )
        except Exception as exc:
            raise RuntimeError("Failed to query rdf_triples for tag clusters") from exc
        rows = resp.data or []
        if not rows:
            break
        for r in rows:
            ids = _parse_cluster_ids(r.get("top_cluster_ids"))
            counter.update(ids)
        if len(rows) < page_size:
            break
        offset += page_size
    # Top N by count
    out = [
        {"id": cid, "label": cid, "count": count}
        for cid, count in counter.most_common(limit)
    ]
    return out


router = APIRouter(tags=["stats"])


@router.get("/stats")
def api_stats():
    """GET /api/stats — document, triple, chunk, and actor counts."""
    return get_stats()


@router.get("/tag-clusters")
def api_tag_clusters():
    """GET /api/tag-clusters — up to 30 semantic tag clusters from rdf_triples.top_cluster_ids."""
    return get_tag_clusters(limit=30)
