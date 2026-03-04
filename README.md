# RAG for Epstein Document Explorer

A research tool that lets you ask natural-language questions over a document corpus and get answers with direct citations to source documents. It combines semantic search, structured relationship data, and an LLM to produce grounded, sourced responses.

**Try it here:** [epsteinfilerag.vercel.app](https://epsteinfilerag.vercel.app)

## Features

- **Q&A with citations** — Ask questions in plain language; answers include source documents and structured facts (actor–action–target triples) you can click through.
- **Entity search** — Search for people and entities; see relationship counts and canonical names.
- **Relationship graph** — Explore entities and their connections in an interactive force-directed graph with filters.
- **Document viewer** — Open any cited document to read the full text.

Sign-in with **Google** (Supabase Auth) is required to use the chat.

## Stack

| Layer      | Tech |
|-----------|------|
| Frontend  | React, Vite, Tailwind, Supabase Auth |
| Backend   | Python, FastAPI |
| Database  | Supabase (PostgreSQL + pgvector) |
| Embeddings| OpenAI `text-embedding-3-small` |
| LLM       | **OpenRouter** (e.g. Llama 3.3) or other OpenAI-compatible (Groq, Ollama, etc.) |

## Quick start

**Backend**

```bash
cd backend
pip install -r requirements.txt
# Copy .env.example to .env. Set SUPABASE_*, OPENAI_API_KEY, and for chat: LLM_BASE_URL, LLM_MODEL, LLM_API_KEY (see backend/.env.example)
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

**Frontend**

```bash
cd frontend
npm install
# Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY (and optionally VITE_API_URL) in .env
npm run dev
```

Open the app (e.g. http://localhost:3000), sign in with Google, then ask a question or switch to Search or Network.

## Data source

The document corpus and extracted entities/relationships come from the [Epstein Document Explorer](https://github.com/maxandrews/Epstein-doc-explorer) project (`document_analysis.db`). This project adds a RAG pipeline (chunking, embedding, retrieval, and LLM generation) on top of that data.

## Docs

- **`docs/BACKEND_PLAN.md`** — Architecture, database design, retrieval pipeline, API, and environment variables.
- **`docs/PROGRESS.md`** — Build phases and current status.
