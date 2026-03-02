# /api/document endpoints: GET /api/document/{doc_id} (metadata), GET /api/document/{doc_id}/text (full text).
# Also get_metadata_for_doc_ids() for enriching chat sources.

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
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

DOC_METADATA_COLS = (
    "doc_id",
    "one_sentence_summary",
    "category",
    "date_range_earliest",
    "date_range_latest",
)


def _create_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def get_metadata_for_doc_ids(doc_ids: List[str]) -> List[Dict[str, Any]]:
    """Fetch document metadata for the given doc_ids; return list in requested order, null-fill missing."""
    if not doc_ids:
        return []
    client = _create_supabase_client()
    try:
        resp = (
            client.table("documents")
            .select(",".join(DOC_METADATA_COLS))
            .in_("doc_id", list(doc_ids))
            .execute()
        )
    except Exception as exc:
        raise RuntimeError("Failed to query documents from Supabase") from exc
    rows = resp.data or []
    by_id = {r["doc_id"]: r for r in rows}
    out: List[Dict[str, Any]] = []
    for doc_id in doc_ids:
        r = by_id.get(doc_id)
        if r is None:
            out.append(
                {
                    "doc_id": doc_id,
                    "one_sentence_summary": None,
                    "category": None,
                    "date_range_earliest": None,
                    "date_range_latest": None,
                }
            )
        else:
            out.append(
                {
                    "doc_id": r.get("doc_id") or doc_id,
                    "one_sentence_summary": r.get("one_sentence_summary"),
                    "category": r.get("category"),
                    "date_range_earliest": r.get("date_range_earliest"),
                    "date_range_latest": r.get("date_range_latest"),
                }
            )
    return out


def get_document_metadata(doc_id: str) -> Dict[str, Any]:
    """Fetch metadata for a single document. Raises HTTPException 404 if not found."""
    client = _create_supabase_client()
    try:
        resp = (
            client.table("documents")
            .select(",".join(DOC_METADATA_COLS))
            .eq("doc_id", doc_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        raise RuntimeError("Failed to query documents from Supabase") from exc
    rows = resp.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Document not found")
    r = rows[0]
    return {
        "doc_id": r.get("doc_id", doc_id),
        "one_sentence_summary": r.get("one_sentence_summary"),
        "category": r.get("category"),
        "date_range_earliest": r.get("date_range_earliest"),
        "date_range_latest": r.get("date_range_latest"),
    }


def get_document_text(doc_id: str) -> str:
    """Fetch full_text for a single document. Raises HTTPException 404 if not found."""
    client = _create_supabase_client()
    try:
        resp = (
            client.table("documents")
            .select("full_text")
            .eq("doc_id", doc_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        raise RuntimeError("Failed to query documents from Supabase") from exc
    rows = resp.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Document not found")
    return rows[0].get("full_text") or ""


router = APIRouter(tags=["documents"])


@router.get("/document/{doc_id}")
def api_get_document(doc_id: str):
    """GET /api/document/{doc_id} — metadata for source cards."""
    return get_document_metadata(doc_id)


@router.get("/document/{doc_id}/text")
def api_get_document_text(doc_id: str):
    """GET /api/document/{doc_id}/text — full text for document viewer."""
    text = get_document_text(doc_id)
    return {"full_text": text}
