"""Single place for query/chunk embeddings: OpenAI or Ollama (e.g. qwen3-embedding:8b)."""

from __future__ import annotations

import json
import urllib.request
from typing import List, Sequence

# Load config from backend (same pattern as other retrieval modules)
import importlib.util
from pathlib import Path

_backend_dir = Path(__file__).resolve().parent.parent
_dotenv_path = _backend_dir / ".env"
if _dotenv_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_dotenv_path, override=True)
_config_py = _backend_dir / "config.py"
_spec = importlib.util.spec_from_file_location("_embed_config", _config_py)
_cfg = importlib.util.module_from_spec(_spec)
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(_cfg)

EMBED_PROVIDER = getattr(_cfg, "EMBED_PROVIDER", "openai")
OPENAI_API_KEY = getattr(_cfg, "OPENAI_API_KEY", "")
OPENAI_EMBED_MODEL = getattr(_cfg, "OPENAI_EMBED_MODEL", "text-embedding-3-small")
OLLAMA_BASE_URL = getattr(_cfg, "OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_EMBED_MODEL = getattr(_cfg, "OLLAMA_EMBED_MODEL", "qwen3-embedding:8b")
EMBED_DIM = getattr(_cfg, "EMBED_DIM", 1536)
EMBED_REQUEST_TIMEOUT = getattr(_cfg, "EMBED_REQUEST_TIMEOUT", 300)


def _ollama_embed(texts: Sequence[str]) -> List[List[float]]:
    """Call Ollama /api/embed; return list of vectors. Uses dimensions=EMBED_DIM for DB compatibility."""
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/embed"
    payload = {
        "model": OLLAMA_EMBED_MODEL,
        "input": list(texts) if len(texts) != 1 else texts[0],
        "dimensions": EMBED_DIM,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=EMBED_REQUEST_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    embeddings = data.get("embeddings")
    if not embeddings:
        raise RuntimeError("Ollama /api/embed returned no embeddings")
    # If single input, Ollama may return one vector; normalize to list of lists
    if isinstance(embeddings[0], (int, float)):
        embeddings = [embeddings]
    return [list(e) for e in embeddings]


def _openai_embed(texts: Sequence[str]) -> List[List[float]]:
    """Call OpenAI embeddings API; return list of vectors."""
    from openai import OpenAI
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set. Set it in backend/.env or use EMBED_PROVIDER=ollama.")
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.embeddings.create(
        model=OPENAI_EMBED_MODEL,
        input=[t.strip() or " " for t in texts],
        timeout=EMBED_REQUEST_TIMEOUT,
    )
    if not response.data or len(response.data) != len(texts):
        raise RuntimeError("OpenAI embeddings returned unexpected count")
    return [item.embedding for item in response.data]


def get_embedding(text: str) -> List[float]:
    """Return embedding vector for a single string (query or chunk)."""
    text = (text or " ").strip()
    if EMBED_PROVIDER == "ollama":
        vectors = _ollama_embed([text])
    else:
        vectors = _openai_embed([text])
    if not vectors:
        raise RuntimeError("No embedding returned")
    return vectors[0]


def get_embeddings_batch(texts: Sequence[str]) -> List[List[float]]:
    """Return list of embedding vectors for multiple strings. Order preserved."""
    if not texts:
        return []
    if EMBED_PROVIDER == "ollama":
        return _ollama_embed(list(texts))
    return _openai_embed(list(texts))
