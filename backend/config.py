# Environment variables, model names, chunk sizes — env only, no hardcoded credentials.
# Use: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

# Supabase (only database per project.mdc)
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
# JWT secret for verifying Supabase Auth tokens (Project Settings -> API -> JWT Secret). Required for /api/chat.
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "").strip()
# Direct Postgres connection string for admin/migration tasks (e.g. create_indexes.py).
# Expected format: postgresql://USER:PASSWORD@HOST:PORT/DB
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL", "")

# SQLite source for Phase 1 migration (document_analysis.db). Prefer env, else backend/data/epstein-doc-explorer.
_BACKEND_DIR = Path(__file__).resolve().parent
SQLITE_DB_PATH = (
    os.getenv("SQLITE_DB_PATH")
    or os.getenv("DOC_EXPLORER_DB_PATH")
    or str(_BACKEND_DIR / "data" / "document_analysis.db")
)

# Embeddings (OpenAI text-embedding-3-small)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

# LLM: provider choice and provider-specific settings.
# LLM_PROVIDER: "anthropic" (Claude) or "openai_compatible" (Groq, Together, OpenRouter, vLLM, Ollama, etc.).
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").strip().lower()

# Anthropic Claude (when LLM_PROVIDER=anthropic). ANTHROPIC_MODEL can be an alias (sonnet, opus, haiku) or a concrete model ID.
# Aliases are resolved once at first use via Models API and cached for the process.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "sonnet")

# LLM API (when LLM_PROVIDER=openai_compatible). Base URL and model name; API key required by some providers (Groq, Together, OpenRouter), optional for local (e.g. Ollama).
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "").strip()
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()

# Chunk sizes (for ingestion)
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "400"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))

# Retrieval pipeline (chat): candidate doc caps and merge
SUMMARY_TOP_K = int(os.getenv("SUMMARY_TOP_K", "20"))
TRIPLE_CANDIDATE_TOP_K = int(os.getenv("TRIPLE_CANDIDATE_TOP_K", "25"))
MAX_CANDIDATE_DOCS = int(os.getenv("MAX_CANDIDATE_DOCS", "40"))
CHUNK_TOP_K = int(os.getenv("CHUNK_TOP_K", "5"))
