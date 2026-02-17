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
