# /api/sessions: CRUD for chat sessions and messages. Requires JWT.

from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from uuid import UUID

from pydantic import BaseModel

from fastapi import APIRouter, Body, HTTPException, status
from supabase import Client, create_client

from api.auth import RequireAuth


class CreateSessionBody(BaseModel):
    title: str = "New chat"

_backend_dir = Path(__file__).resolve().parent.parent
_config_py = _backend_dir / "config.py"
_spec = importlib.util.spec_from_file_location("_sessions_config", _config_py)
assert _spec is not None and _spec.loader is not None
_sessions_config = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sessions_config)
SUPABASE_URL = getattr(_sessions_config, "SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = getattr(_sessions_config, "SUPABASE_SERVICE_ROLE_KEY", "")


def _client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


router = APIRouter(tags=["sessions"])


def _session_belongs_to_user(client: Client, session_id: str, user_id: UUID) -> bool:
    r = client.table("chat_sessions").select("id").eq("id", session_id).eq("user_id", str(user_id)).execute()
    return bool(r.data and len(r.data) == 1)


@router.post("/sessions")
def create_session(
    user_id: RequireAuth,
    body: CreateSessionBody | None = Body(None),
) -> Dict[str, Any]:
    """Create a new chat session for the current user."""
    title = (body and body.title) or "New chat"
    client = _client()
    row = {
        "user_id": str(user_id),
        "title": title,
    }
    r = client.table("chat_sessions").insert(row).execute()
    if not r.data or len(r.data) == 0:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create session")
    s = r.data[0]
    return {"id": s["id"], "title": s["title"], "created_at": s["created_at"]}


@router.get("/sessions")
def list_sessions(user_id: RequireAuth) -> List[Dict[str, Any]]:
    """List chat sessions for the current user, newest first."""
    client = _client()
    r = (
        client.table("chat_sessions")
        .select("id,title,created_at,updated_at")
        .eq("user_id", str(user_id))
        .order("updated_at", desc=True)
        .execute()
    )
    return list(r.data or [])


@router.get("/sessions/{session_id}")
def get_session_messages(session_id: UUID, user_id: RequireAuth) -> List[Dict[str, Any]]:
    """Get all messages for a session. Returns 404 if session not found or not owned by user."""
    client = _client()
    if not _session_belongs_to_user(client, str(session_id), user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    r = (
        client.table("chat_messages")
        .select("id,role,content,sources,triples,created_at")
        .eq("session_id", str(session_id))
        .order("created_at", desc=False)
        .execute()
    )
    rows = r.data or []
    out: List[Dict[str, Any]] = []
    for row in rows:
        out.append({
            **row,
            "sources": row.get("sources") if row.get("sources") is not None else [],
            "triples": row.get("triples") if row.get("triples") is not None else [],
        })
    return out


@router.delete("/sessions/{session_id}")
def delete_session(session_id: UUID, user_id: RequireAuth) -> Dict[str, str]:
    """Delete a session and its messages. Returns 404 if not owned by user."""
    client = _client()
    if not _session_belongs_to_user(client, str(session_id), user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    client.table("chat_sessions").delete().eq("id", str(session_id)).execute()
    return {"status": "deleted"}


def append_chat_turn(
    session_id: UUID,
    user_id: UUID,
    user_content: str,
    assistant_content: str,
    sources: List[Dict[str, Any]],
    triples: List[Dict[str, Any]],
    session_title: str | None = None,
) -> None:
    """Append one user message and one assistant message to a session; update session updated_at. If session_title is set, use it (e.g. first message)."""
    sources = list(sources) if sources is not None else []
    triples = list(triples) if triples is not None else []
    client = _client()
    if not _session_belongs_to_user(client, str(session_id), user_id):
        return
    sid = str(session_id)
    now = datetime.now(timezone.utc).isoformat()
    # Check if this is the first message so we can set title
    r = client.table("chat_messages").select("*", count="exact").eq("session_id", sid).execute()
    first_message = (getattr(r, "count", None) or 0) == 0
    # Include sources/triples for every row (user messages use []).
    user_sources: List[Dict[str, Any]] = []
    user_triples: List[Dict[str, Any]] = []
    client.table("chat_messages").insert(
        [
            {
                "session_id": sid,
                "role": "user",
                "content": user_content,
                "sources": user_sources,
                "triples": user_triples,
            },
            {
                "session_id": sid,
                "role": "assistant",
                "content": assistant_content,
                "sources": sources,
                "triples": triples,
            },
        ]
    ).execute()
    update: Dict[str, Any] = {"updated_at": now}
    if first_message and session_title:
        update["title"] = session_title
    client.table("chat_sessions").update(update).eq("id", sid).execute()
