# Session CRUD for anonymous chat persistence: POST/GET/DELETE /api/sessions, GET /api/sessions/{id}.
# Keyed by device_id (X-Device-Id header) instead of JWT user_id.

from __future__ import annotations

import importlib.util
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from pydantic import BaseModel

from fastapi import APIRouter, Body, HTTPException, status
from supabase import Client, create_client

from api.auth import RequireDeviceId


class CreateSessionBody(BaseModel):
    title: str | None = None

_backend_dir = Path(__file__).resolve().parent.parent
_config_py = _backend_dir / "config.py"
_spec = importlib.util.spec_from_file_location("_env_config", _config_py)
_env_config = importlib.util.module_from_spec(_spec)
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(_env_config)

SUPABASE_URL: str = getattr(_env_config, "SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY: str = getattr(_env_config, "SUPABASE_SERVICE_ROLE_KEY", "")


def _create_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def _session_row(s: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(s["id"]),
        "title": s.get("title"),
        "created_at": s.get("created_at"),
        "updated_at": s.get("updated_at"),
    }


def _message_row(m: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "role": m.get("role"),
        "content": m.get("content"),
        "sources": m.get("sources"),
        "triples": m.get("triples"),
        "created_at": m.get("created_at"),
    }


router = APIRouter(tags=["sessions"])


@router.post("/sessions")
def create_session(
    device_id: RequireDeviceId,
    body: CreateSessionBody | None = Body(None),
):
    """Create a new anonymous chat session. Body optional: { "title": "New chat" }."""
    title = (body.title if body else None) or "New chat"
    session_id = uuid4()
    now_iso = datetime.now(timezone.utc).isoformat()
    client = _create_supabase_client()
    try:
        client.table("chat_sessions_anonymous").insert(
            {
                "id": str(session_id),
                "device_id": device_id,
                "title": title,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
        ).execute()
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {e!s}",
        ) from e
    return {
        "id": str(session_id),
        "title": title,
        "created_at": now_iso,
        "updated_at": now_iso,
    }


@router.get("/sessions")
def list_sessions(
    device_id: RequireDeviceId,
    limit: int = 50,
):
    """List anonymous sessions for this device, most recently updated first."""
    client = _create_supabase_client()
    try:
        resp = (
            client.table("chat_sessions_anonymous")
            .select("id, title, created_at, updated_at")
            .eq("device_id", device_id)
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list sessions",
        ) from e
    rows = resp.data or []
    return [_session_row(r) for r in rows]


@router.get("/sessions/{session_id}")
def get_session(
    session_id: str,
    device_id: RequireDeviceId,
):
    """Get one session and its messages. 404 if not found or not owned by device."""
    client = _create_supabase_client()
    try:
        sess_resp = (
            client.table("chat_sessions_anonymous")
            .select("id, title, created_at, updated_at")
            .eq("id", session_id)
            .eq("device_id", device_id)
            .limit(1)
            .execute()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load session",
        ) from e
    sess_rows = sess_resp.data or []
    if not sess_rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    session = _session_row(sess_rows[0])

    try:
        msg_resp = (
            client.table("chat_messages_anonymous")
            .select("role, content, sources, triples, created_at")
            .eq("session_id", session_id)
            .order("created_at")
            .execute()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load messages",
        ) from e
    messages = [_message_row(m) for m in (msg_resp.data or [])]
    return {"session": session, "messages": messages}


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    device_id: RequireDeviceId,
):
    """Delete a session and its messages. 404 if not found or not owned by device."""
    client = _create_supabase_client()
    try:
        resp = (
            client.table("chat_sessions_anonymous")
            .delete()
            .eq("id", session_id)
            .eq("device_id", device_id)
            .execute()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete session",
        ) from e
    if not (resp.data or resp.count):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return {"ok": True}
