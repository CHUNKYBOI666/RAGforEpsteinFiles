"""Stage 6: send assembled context to LLM (OpenAI-compatible API); return answer, sources, triples."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict, List

from openai import OpenAI as OpenAIClient

# Load backend config (env only)
_backend_dir = Path(__file__).resolve().parent.parent
_config_py = _backend_dir / "config.py"
_spec = importlib.util.spec_from_file_location("_env_config", _config_py)
_env_config = importlib.util.module_from_spec(_spec)
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(_env_config)

LLM_BASE_URL: str = getattr(_env_config, "LLM_BASE_URL", "").strip()
LLM_MODEL: str = getattr(_env_config, "LLM_MODEL", "").strip()
LLM_API_KEY: str = getattr(_env_config, "LLM_API_KEY", "").strip()

DEFAULT_MAX_TOKENS = 1024


def _validate_config() -> None:
    if not LLM_BASE_URL or not LLM_MODEL:
        raise ValueError(
            "LLM_BASE_URL or LLM_MODEL is not set. "
            "Set both in backend/.env (and LLM_API_KEY if the provider requires it)."
        )


def _call_llm(system_prompt: str, user_prompt: str) -> str:
    """Call OpenAI-compatible chat completions API; return response text."""
    api_key = LLM_API_KEY if LLM_API_KEY else "ollama"
    client = OpenAIClient(base_url=LLM_BASE_URL, api_key=api_key)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    response = client.chat.completions.create(
        model=LLM_MODEL,
        max_tokens=DEFAULT_MAX_TOKENS,
        messages=messages,
    )
    answer = ""
    if response.choices and len(response.choices) > 0:
        msg = response.choices[0].message
        if msg and getattr(msg, "content", None):
            answer = msg.content or ""
    return answer


def generate_answer(
    system_prompt: str,
    user_prompt: str,
    doc_ids: List[str],
    triples: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Call LLM with the assembled context; return answer, sources, triples.

    Uses the OpenAI-compatible chat API (OpenRouter, Groq, Together, vLLM, Ollama, etc.)
    configured via LLM_BASE_URL, LLM_MODEL, and LLM_API_KEY.

    Args:
        system_prompt: System instruction (cite doc_ids, use only context).
        user_prompt: Question + retrieved chunks + triples + "Answer:".
        doc_ids: Source document IDs used in context (for sources list).
        triples: Structured facts from triple_lookup (returned as-is).

    Returns:
        Dict with:
          - "answer": str (LLM prose response)
          - "sources": list of {"doc_id": str} (one per doc_id)
          - "triples": list of triple dicts (actor, action, target, timestamp, location, doc_id)
    """
    _validate_config()
    answer = _call_llm(system_prompt, user_prompt)

    sources = [{"doc_id": str(doc_id)} for doc_id in doc_ids]
    triples_out: List[Dict[str, Any]] = []
    for t in triples or []:
        triples_out.append(
            {
                "actor": t.get("actor") or "",
                "action": t.get("action") or "",
                "target": t.get("target") or "",
                "timestamp": t.get("timestamp") or "",
                "location": t.get("location") or "",
                "doc_id": str(t.get("doc_id") or ""),
            }
        )

    return {
        "answer": answer.strip(),
        "sources": sources,
        "triples": triples_out,
    }
