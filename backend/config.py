# Environment variables, model names, chunk sizes — env only, no hardcoded credentials.
# Use: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Supabase (only database per project.mdc)
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
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

# LLM (Anthropic Claude)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")

# Chunk sizes (for ingestion)
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "400"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
