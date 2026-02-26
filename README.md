# RAGforEFN

Monorepo layout:

- **`frontend/`** — Vite/React UI (from Google AI Studio). Run: `cd frontend && npm install && npm run dev`
- **`backend/`** — Python FastAPI + Supabase RAG (ingestion, retrieval, api). See `docs/BACKEND_PLAN.md` and `backend/README.md`. Run from `backend/`: `pip install -r requirements.txt`, then run ingestion/API per plan.

Root config (e.g. `.env`) can live at repo root or in `backend/` for API keys and in `frontend/` for frontend env.
