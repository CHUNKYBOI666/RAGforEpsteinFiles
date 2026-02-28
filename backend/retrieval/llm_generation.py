"""Stage 6: send assembled context to Claude; return answer, sources, triples."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict, List

from anthropic import Anthropic
from anthropic import NotFoundError as AnthropicNotFoundError

# Load backend config (env only)
_backend_dir = Path(__file__).resolve().parent.parent
_config_py = _backend_dir / "config.py"
_spec = importlib.util.spec_from_file_location("_env_config", _config_py)
_env_config = importlib.util.module_from_spec(_spec)
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(_env_config)

ANTHROPIC_API_KEY: str = getattr(_env_config, "ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL: str = getattr(_env_config, "ANTHROPIC_MODEL", "sonnet")

DEFAULT_MAX_TOKENS = 1024

# Aliases supported by Models API retrieve(); Messages API requires concrete ID, so we resolve once and cache.
_ANTHROPIC_ALIASES = frozenset({"sonnet", "opus", "haiku"})
_model_id_cache: str | None = None


def _get_model_id_for_messages() -> str:
    """Return model ID for Messages API: resolve alias via Models API once and cache; otherwise use as-is."""
    global _model_id_cache
    if _model_id_cache is not None:
        return _model_id_cache
    raw = (ANTHROPIC_MODEL or "").strip()
    if raw.lower() in _ANTHROPIC_ALIASES:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        try:
            info = client.models.retrieve(raw)
            _model_id_cache = info.id
        except AnthropicNotFoundError:
            # Alias not supported by retrieve() for this key; resolve from list (first matching family).
            page = client.models.list()
            alias_lower = raw.lower()
            for m in page.data:
                if alias_lower in (m.id or "").lower():
                    _model_id_cache = m.id
                    break
            if _model_id_cache is None:
                raise ValueError(
                    f"ANTHROPIC_MODEL={raw!r} (alias) could not be resolved: "
                    "retrieve() returned 404 and no matching model in list(). "
                    "Set ANTHROPIC_MODEL to a concrete model ID in .env (e.g. claude-sonnet-4-6)."
                ) from None
        return _model_id_cache
    _model_id_cache = raw or "sonnet"  # fallback; will fail later if invalid
    return _model_id_cache


def _validate_config() -> None:
    if not ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY is not set. Set it in backend/.env or your environment."
        )


def generate_answer(
    system_prompt: str,
    user_prompt: str,
    doc_ids: List[str],
    triples: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Call Claude with the assembled context; return answer, sources, triples.

    Args:
        system_prompt: System instruction (cite doc_ids, use only context).
        user_prompt: Question + retrieved chunks + triples + "Answer:".
        doc_ids: Source document IDs used in context (for sources list).
        triples: Structured facts from triple_lookup (returned as-is).

    Returns:
        Dict with:
          - "answer": str (Claude's prose response)
          - "sources": list of {"doc_id": str} (one per doc_id)
          - "triples": list of triple dicts (actor, action, target, timestamp, location, doc_id)
    """
    _validate_config()

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    model_id = _get_model_id_for_messages()

    message = client.messages.create(
        model=model_id,
        max_tokens=DEFAULT_MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    # Extract text from first content block
    answer = ""
    if message.content and len(message.content) > 0:
        block = message.content[0]
        if hasattr(block, "text"):
            answer = block.text or ""

    # sources: one entry per doc_id (minimal for Phase 4; Phase 5 can enrich with document metadata)
    sources = [{"doc_id": str(doc_id)} for doc_id in doc_ids]

    # triples: same list we sent in context (from triple_lookup)
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
