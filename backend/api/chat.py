# /api/chat endpoint: runs full 6-stage retrieval pipeline, returns answer + sources + triples.
# Optional session_id: persist user + assistant messages to that session.

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from openai import OpenAI
from supabase import Client, create_client

from api.auth import RequireAuth

# Backend config (load config.py file, not config package) and retrieval stages
import importlib.util
import sys
from pathlib import Path

_backend = Path(__file__).resolve().parent.parent
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

_config_py = _backend / "config.py"
_spec = importlib.util.spec_from_file_location("_backend_config", _config_py)
_backend_config = importlib.util.module_from_spec(_spec)
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(_backend_config)

OPENAI_API_KEY = getattr(_backend_config, "OPENAI_API_KEY", "")
OPENAI_EMBED_MODEL = getattr(_backend_config, "OPENAI_EMBED_MODEL", "text-embedding-3-small")
SUPABASE_URL = getattr(_backend_config, "SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = getattr(_backend_config, "SUPABASE_SERVICE_ROLE_KEY", "")

from api.documents import get_metadata_for_doc_ids


def _create_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def _verify_session_owner(session_id: str, user_id) -> bool:
    """Return True if session exists and belongs to user_id."""
    client = _create_supabase_client()
    resp = (
        client.table("chat_sessions")
        .select("id")
        .eq("id", session_id)
        .eq("user_id", str(user_id))
        .limit(1)
        .execute()
    )
    return bool(resp.data and len(resp.data) > 0)


def _persist_turn(session_id: str, query: str, result: Dict[str, Any]) -> None:
    from datetime import datetime, timezone

    client = _create_supabase_client()
    # Check if this is the first message (no messages yet) to set session title
    msg_resp = client.table("chat_messages").select("id").eq("session_id", session_id).execute()
    is_first = len(msg_resp.data or []) == 0

    # Insert user message
    client.table("chat_messages").insert(
        {"session_id": session_id, "role": "user", "content": query, "sources": None, "triples": None}
    ).execute()
    # Insert assistant message
    client.table("chat_messages").insert(
        {
            "session_id": session_id,
            "role": "assistant",
            "content": result.get("answer") or "",
            "sources": result.get("sources") or [],
            "triples": result.get("triples") or [],
        }
    ).execute()

    # Update session updated_at; set title from first query if this was the first turn
    now_iso = datetime.now(timezone.utc).isoformat()
    update_payload: Dict[str, Any] = {"updated_at": now_iso}
    if is_first and query:
        update_payload["title"] = (query[:50] + "…") if len(query) > 50 else query
    client.table("chat_sessions").update(update_payload).eq("id", session_id).execute()
from retrieval.context_builder import build_context_prompt
from retrieval.chunk_search import chunk_search
from retrieval.llm_generation import generate_answer
from retrieval.query_expansion import expand_query
from retrieval.summary_search import summary_search
from retrieval.triple_candidate_search import get_doc_ids_by_triple_terms
from retrieval.triple_lookup import triple_lookup

SUMMARY_TOP_K = getattr(_backend_config, "SUMMARY_TOP_K", 20)
TRIPLE_CANDIDATE_TOP_K = getattr(_backend_config, "TRIPLE_CANDIDATE_TOP_K", 25)
MAX_CANDIDATE_DOCS = getattr(_backend_config, "MAX_CANDIDATE_DOCS", 40)
CHUNK_TOP_K = getattr(_backend_config, "CHUNK_TOP_K", 5)


def _merge_and_cap_candidates(
    summary_doc_ids: List[str],
    triple_doc_ids: List[str],
    max_total: int,
) -> List[str]:
    """Merge summary-based and triple-based doc_ids; prefer summary order, cap at max_total."""
    seen = set()
    merged: List[str] = []
    for doc_id in summary_doc_ids:
        if doc_id and doc_id not in seen and len(merged) < max_total:
            seen.add(doc_id)
            merged.append(doc_id)
    for doc_id in triple_doc_ids:
        if doc_id and doc_id not in seen and len(merged) < max_total:
            seen.add(doc_id)
            merged.append(doc_id)
    return merged


def _get_query_embedding(query: str) -> List[float]:
    """Embed the user query with OpenAI text-embedding-3-small (1536 dims)."""
    if not OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY is not set. Set it in backend/.env or your environment."
        )
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.embeddings.create(
        model=OPENAI_EMBED_MODEL,
        input=[query.strip() or " "],
    )
    if not response.data or len(response.data) == 0:
        raise RuntimeError("OpenAI embeddings returned no data")
    return response.data[0].embedding


def run_chat_pipeline(query: str) -> Dict[str, Any]:
    """Run the full 6-stage RAG pipeline and return answer, sources, triples.

    Stages:
        1. Query expansion (entity_aliases, tokenized for multi-word queries)
        2. Summary-level search + triple-based candidate expansion -> merged candidate doc_ids
        3. Chunk-level search -> top chunks
        4. Triple lookup for those doc_ids
        5. Context assembly (prompt)
        6. LLM generation (Claude)

    Returns:
        Dict with "answer" (str), "sources" (list), "triples" (list).
        sources and triples are empty lists when none; never omitted.
    """
    query = (query or "").strip()
    if not query:
        return {
            "answer": "Please ask a question about the documents.",
            "sources": [],
            "triples": [],
        }

    # Stage 1: query expansion
    search_terms = expand_query(query)

    # Embed query for vector search (used in stages 2 and 3)
    query_embedding = _get_query_embedding(query)

    # Stage 2: summary-level search + triple-based candidate expansion -> merged candidate doc_ids
    summary_doc_ids = summary_search(query_embedding, top_k=SUMMARY_TOP_K)
    try:
        triple_doc_ids = get_doc_ids_by_triple_terms(search_terms, top_k=TRIPLE_CANDIDATE_TOP_K)
    except Exception:
        # If triple-based candidate expansion fails (e.g., RPC timeout), fall back to summary-only.
        triple_doc_ids = []
    candidate_doc_ids = _merge_and_cap_candidates(
        summary_doc_ids, triple_doc_ids, max_total=MAX_CANDIDATE_DOCS
    )

    # Stage 3: chunk-level search within candidates
    chunks = chunk_search(
        query_embedding,
        candidate_doc_ids,
        top_k=CHUNK_TOP_K,
    )

    # Stage 4: triple lookup (use expanded terms; doc_ids from chunks)
    doc_ids_for_triples = list({c.get("doc_id") for c in chunks if c.get("doc_id")})
    terms_for_triples = list(search_terms) if search_terms else [query]
    triples = triple_lookup(doc_ids_for_triples, terms_for_triples)

    # Stage 5: context assembly
    context_result = build_context_prompt(query, chunks, triples)
    system_prompt = context_result["system_prompt"]
    user_prompt = context_result["user_prompt"]
    doc_ids = context_result["doc_ids"]

    # Stage 6: LLM generation
    result = generate_answer(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        doc_ids=doc_ids,
        triples=triples,
    )

    return {
        "answer": result["answer"],
        "sources": result["sources"],
        "triples": result["triples"],
    }


router = APIRouter(tags=["chat"])


@router.get("/chat")
def api_chat(
    q: str = Query(..., description="Natural language question"),
    session_id: Optional[str] = Query(None, description="If provided, persist this turn to the session"),
    user_id: RequireAuth = None,  # Injected by FastAPI (still required for access control)
):
    """GET /api/chat?q= — run RAG pipeline, return answer + enriched sources + triples. Requires Authorization: Bearer <token>. Optional session_id to save the turn."""
    if session_id and not _verify_session_owner(session_id, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    result = run_chat_pipeline(q)
    doc_ids = [s.get("doc_id") for s in result["sources"] if s.get("doc_id")]
    if doc_ids:
        result["sources"] = get_metadata_for_doc_ids(doc_ids)

    if session_id:
        _persist_turn(session_id, q.strip(), result)

    return result
