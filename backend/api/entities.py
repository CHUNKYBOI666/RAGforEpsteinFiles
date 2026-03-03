# GET /api/entities — preset list of all graph entities (name + count) for client-side suggestion filtering.

from __future__ import annotations

import importlib.util
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


def _create_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


DEFAULT_LIMIT = 2000


def get_entity_preset_list(limit: int = DEFAULT_LIMIT) -> List[Dict[str, Any]]:
    """Return all entities (actor/target) with relationship counts via RPC. One round-trip."""
    client = _create_supabase_client()
    try:
        resp = client.rpc("get_entity_preset_list", {"max_entities": limit}).execute()
    except Exception:
        # RPC may not exist yet; run backend/ingestion/rpc_entity_preset_list.sql in Supabase
        return []
    rows = resp.data or []
    return [{"canonical_name": r.get("canonical_name"), "count": r.get("count") or 0} for r in rows]


router = APIRouter(tags=["entities"])


@router.get("/entities")
def api_entities():
    """GET /api/entities — preset list of entity names + counts for graph suggestion dropdown."""
    return get_entity_preset_list()
