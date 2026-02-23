"""Env-based config. Single source for dataset name, paths, and later Qdrant/embedding."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# HF dataset
HF_DATASET_NAME: str = os.getenv("HF_DATASET_NAME", "teyler/epstein-files-20k")

# Paths (optional)
DATA_DIR: Path = Path(os.getenv("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Embedding (BGE)
EMBED_MODEL_NAME: str = os.getenv("EMBED_MODEL_NAME", "bge-base-en-v1.5")
EMBED_DOCUMENT_PREFIX: str = os.getenv(
    "EMBED_DOCUMENT_PREFIX",
    "Represent this document for retrieval: ",
)
EMBED_QUERY_PREFIX: str = os.getenv(
    "EMBED_QUERY_PREFIX",
    "Represent this question for retrieving relevant documents: ",
)
EMBED_BATCH_SIZE: int = int(os.getenv("EMBED_BATCH_SIZE", "64"))
EMBED_DEVICE: str | None = os.getenv("EMBED_DEVICE")  # None = auto (cuda/mps/cpu)

# Qdrant (local persistent only; no in-memory)
QDRANT_PATH: Path = Path(os.getenv("QDRANT_PATH", "./data/qdrant"))
QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "epstein_files")

# LLM (for /chat)
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")  # "openai" or "local"
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE: str | None = os.getenv("OPENAI_API_BASE")  # for local OpenAI-compatible server
