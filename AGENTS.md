# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

RAGforEFN is a monorepo with two services: a Python/FastAPI **backend** (`backend/`) and a Vite/React **frontend** (`frontend/`). See `README.md` for basics.

### Services

| Service | Dir | Start command | Port |
|---------|-----|---------------|------|
| Backend (FastAPI) | `backend/` | `cd backend && source .venv/bin/activate && uvicorn src.api.app:app --host 0.0.0.0 --port 8000` | 8000 |
| Frontend (Vite) | `frontend/` | `cd frontend && npm run dev` | 3000 |

### Non-obvious caveats

- **Backend venv**: The backend uses a Python venv at `backend/.venv`. Always activate it before running backend commands: `source backend/.venv/bin/activate`.
- **`python3.12-venv` package**: The system Python may not have `ensurepip`. If `python3 -m venv` fails, install `python3.12-venv` via apt.
- **No Qdrant index by default**: The `/search` and `/chat` endpoints return 503 until the ingestion pipeline is run (`cd backend && source .venv/bin/activate && python scripts/run_ingestion.py`). Ingestion requires external data repos to be cloned (see `backend/.env.example`). The frontend gracefully falls back to mock data when the backend is unavailable or returns errors.
- **Frontend lint**: `npm run lint` (which runs `tsc --noEmit`) has a pre-existing error on `import.meta.env` because `tsconfig.json` does not include `vite/client` types. The app builds and runs fine regardless.
- **Backend config module**: The backend uses `from config import settings` which resolves to `backend/config/settings.py`. This only works when running from the `backend/` directory.
- **Tests**: Run backend tests with `cd backend && source .venv/bin/activate && pytest tests/ -v`. One test (`test_search_valid_returns_200_and_structure`) skips without a Qdrant index.
- **CORS**: The backend allows origins on ports 3000 and 5173.
- **LLM (optional)**: The `/chat` endpoint needs `OPENAI_API_KEY` or `OPENAI_API_BASE` set in `backend/.env` to synthesize answers. Without it, `/chat` returns 503 or a fallback message. `/search` works without LLM config.
