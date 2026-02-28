# /api/chat endpoint: runs full 6-stage retrieval pipeline, returns answer + sources + triples.

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Query
from openai import OpenAI

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
from api.documents import get_metadata_for_doc_ids
from retrieval.context_builder import build_context_prompt
from retrieval.chunk_search import chunk_search
from retrieval.llm_generation import generate_answer
from retrieval.query_expansion import expand_query
from retrieval.summary_search import summary_search
from retrieval.triple_lookup import triple_lookup

SUMMARY_TOP_K = 20
CHUNK_TOP_K = 5


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
        1. Query expansion (entity_aliases)
        2. Summary-level search -> candidate doc_ids
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

    # Stage 2: summary-level search -> candidate doc_ids
    candidate_doc_ids = summary_search(query_embedding, top_k=SUMMARY_TOP_K)

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
def api_chat(q: str = Query(..., description="Natural language question")):
    """GET /api/chat?q= — run RAG pipeline, return answer + enriched sources + triples."""
    result = run_chat_pipeline(q)
    doc_ids = [s.get("doc_id") for s in result["sources"] if s.get("doc_id")]
    if doc_ids:
        result["sources"] = get_metadata_for_doc_ids(doc_ids)
    return result
