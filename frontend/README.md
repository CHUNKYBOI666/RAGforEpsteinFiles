# RAGforEFN frontend

Vite + React UI for search and chat over the document index. Left: query + answer; right: evidence panel.

## Run locally

```bash
npm install
npm run dev
```

Defaults to `http://localhost:5173`. Set `VITE_API_URL` (e.g. in `.env.local`) if the API is elsewhere (default `http://localhost:8000`).

## Stack

React, Vite, Tailwind, Motion. Backend: FastAPI at `backend/`; see repo root `README.md` and `BACKEND_PLAN.md`.
