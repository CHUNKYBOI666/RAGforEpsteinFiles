# RAGforEFN

Monorepo layout:

- **`frontend/`** — Vite/React UI (from Google AI Studio). Run: `cd frontend && npm install && npm run dev`
- **`backend/`** — Python FastAPI + RAG (ingestion, Qdrant, API). See `backend/README.md`. Run from `backend/`: `pip install -r requirements.txt`, `python scripts/run_ingestion.py`, etc.

Root config (e.g. `.env`) can live at repo root or in `backend/` for API keys and in `frontend/` for frontend env.
