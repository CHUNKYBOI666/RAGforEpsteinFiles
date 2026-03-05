# Learning Experience — RAG for Epstein Document Explorer

A journal of what was learned, problems encountered, and how they were solved across sessions and the codebase. The last section generalizes these into reusable concepts for future projects.

---

## 1. Session journal

### Session 1 — Vercel deployment and redeploy (transcript: `51f0f1df-cdd9-44d6-b46f-88b6db44c1e7`)

**Topics covered:**

- **Deleting and recreating a Vercel project** — Whether you can delete a deployed project and recreate it (e.g. to “reset” first-24-hour metrics). Outcome: yes, technically; domain is freed; env vars and settings must be reconfigured. Caveat: if the goal is to game a program (Product Hunt, hackathon), rules often forbid relaunching.
- **Steps to redeploy on Vercel** — Two paths: (A) redeploy existing project (Git push, dashboard Redeploy, or `vercel --prod`); (B) delete project then re-import repo at vercel.com/new and re-add domain and env vars.
- **Vercel project settings for this app** — Framework preset (Vite), root directory (`frontend`), build command (`npm run build`), output directory (`dist`), and required env vars: `VITE_API_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`. Note: Vercel deploys only the frontend; backend (FastAPI) must be hosted elsewhere; CORS must allow the Vercel domain.
- **Build command choice** — `npm run build` vs `vite build`: use `npm run build` so the platform runs the script defined in `package.json` and has correct PATH for local tooling.

### Session 2 — Mobile-responsive UI (transcript: `ba2c6d2c-31c3-4b96-8297-c87a8772439c`)

**Topics covered:**

- **Making the webapp clean and responsive on mobile** — Layout and UX were adjusted so the app works well on small screens.
- **Changes made:**
  - **Header:** Stacks vertically on small screens; mode switcher is icon-only on mobile (Synthesize, Raw Search, Network), full labels on desktop; touch targets at least 44px; auth (sign in / log out) next to logo on mobile.
  - **Main content:** Chat and evidence panel stack vertically on mobile (chat on top, evidence below); side-by-side from `md` and up. Graph mode: graph on top, settings sidebar below on mobile.
  - **Typography and spacing:** Smaller hero on mobile; reduced padding; `break-words` on query text to avoid overflow.
  - **Modals:** Document and auth modals use `max-h-[90vh]` and safe margins; larger tap target for Google sign-in; `overscroll-contain` to avoid background scroll when modals are open.
  - **Evidence cards:** Long doc IDs truncated; snippets limited (e.g. `line-clamp-4`) for compact cards.
  - **Device behavior:** `viewport-fit=cover` for notched devices; `pb-safe` for home indicator; `-webkit-tap-highlight-color: transparent` to reduce tap flash.

### Session 3 — Chat sessions: 404 after login, 500 on create session, Supabase client API

**Questions asked:**

1. **Multi-turn in one chat** — Does the plan let users ask new questions on top of the first one in a session? Can they keep asking in the same chat? **Answer:** Yes. Same `session_id` is sent for every message in that chat; the backend appends each user + assistant turn to `chat_messages`. RAG stays one-question-one-answer; persistence is for history only.
2. **How to test locally** — Step-by-step: run `schema_chat_sessions.sql` in Supabase once, set env (SUPABASE_*, OPENAI_*, LLM_*), run backend and frontend, sign in, then test New chat → ask questions → check sidebar → reopen/delete sessions.
3. **404 after login** — User saw “Failed to load resource: 404” with a long hash fragment (access_token, expires_at, etc.). **Explanation:** That URL is the OAuth redirect. The 404 can be (a) wrong Supabase redirect URL, (b) frontend not running at that URL, or (c) a request the page makes after load (e.g. wrong API URL). Redirect URLs in Supabase were correct (`http://localhost:5173`); the real issue turned out to be elsewhere.
4. **Is the redirect correct?** — User shared Supabase URL Configuration (Site URL, Redirect URLs). **Answer:** Yes. `http://localhost:5173` in Redirect URLs is correct for local Vite dev.
5. **DEPLOYMENT_NOT_FOUND 404** — User saw “404: NOT_FOUND”, “DEPLOYMENT_NOT_FOUND”, and an id like `yul1::jrnc4-...`. **Explanation:** That’s a **Vercel** error (not Render). It means the URL they opened (e.g. production Site URL) has no deployment — frontend wasn’t deployed to Vercel yet. Render (backend) doesn’t return that message; no “redirect URL” fix needed on Render.
6. **Backend only on Render, not Vercel — wrong URL in Render?** — Clarified: Supabase redirect goes to the **frontend** URL (localhost or Vercel). Render is the API; set `VITE_API_URL` to the Render backend URL when the frontend calls it. No redirect URL for auth is set on Render.
7. **POST /api/sessions 500 when sending first chat message** — User got “Network response was not ok” and 500 from `POST http://localhost:8000/api/sessions`. We needed the real server error.
8. **“Let’s see the real error”** — We added in `api/sessions.py`: `traceback.print_exc()` and `detail=f"Failed to create session: {e!s}"` in the `create_session` except block so the terminal and response body show the actual exception.
9. **Do I need to rerun the backend?** — Only if uvicorn was started **without** `--reload`. With `--reload`, file changes are picked up automatically.
10. **Command to run backend with reload** — `cd backend && source .venv/bin/activate && python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload`.
11. **Making sense of the terminal error** — The traceback showed: `AttributeError: 'SyncQueryRequestBuilder' object has no attribute 'select'` at `sessions.py` line 75 (`.select("id, title, created_at, updated_at")` after `.insert(...)`). So the Supabase Python client in use doesn’t support chaining `.select()` after `.insert()`.
12. **Sign out / multi-user behavior** — When a user signs out, what happens? If another user signs in and has three sessions, then the first user signs in again, what do they see? **Answer:** Sessions are keyed by `user_id` (JWT `sub`). Sign out does **not** delete data; it only clears the UI’s token. When the same user signs back in, they see **all their previous sessions**. A different user only ever sees **their own** sessions (list/get/delete and chat persistence all filter by `user_id`).

**What we did to fix the 500:**

1. **Surfaced the real error** — In `create_session`, on exception we now call `traceback.print_exc()` and raise `HTTPException(500, detail=f"Failed to create session: {e!s}")` so the terminal gets the full traceback and the response body gets the exception message.
2. **Fixed Supabase client usage** — The client’s `insert()` returns a `SyncQueryRequestBuilder` that has **no `.select()` method** in this version. We changed the flow to: (a) generate `session_id = uuid4()` and `now_iso = datetime.now(timezone.utc).isoformat()` in Python; (b) insert a row with `id`, `user_id`, `title`, `created_at`, `updated_at`; (c) call `.execute()` only (no `.select()`); (d) return the session dict we already have (`id`, `title`, `created_at`, `updated_at`) so we don’t need to read the row back from the DB. This avoids relying on an insert-return pattern that the client doesn’t support.

**Reflection:** Debugging a 500 without a traceback is slow. Always log or re-raise the underlying exception (and optionally include a safe message in the response) so you see the real cause. Supabase’s Python client API can differ between versions (e.g. insert + select chaining); when something like `.select()` isn’t there, fall back to a pattern that doesn’t depend on it (e.g. generate IDs and timestamps in the app and return them after insert). User/session isolation (sessions per `user_id`, sign out not deleting data, each user only seeing their own chats) was already correct; the only bug was the create-session call.

---

## 2. What I learned (from sessions and codebase)

### Deployment (Vercel)

- **Monorepo / subfolder frontends:** When the app lives in a subfolder (e.g. `frontend/`), set **Root Directory** in Vercel to that folder so build and env resolution run in the right place.
- **Framework detection:** Vercel infers framework from `package.json` in the root directory. For Vite, build command defaults to `vite build` and output to `dist`; using **`npm run build`** is still preferred so the script is the single source of truth.
- **Frontend-only on Vercel:** This project uses a separate Python/FastAPI backend. Vercel only serves the static/SPA frontend. The backend must be deployed elsewhere (e.g. Railway, Render, Fly.io), and `VITE_API_URL` must point to that URL in Production (and Preview if needed).
- **Env vars at build time:** Vite only exposes variables prefixed with `VITE_` to the client. All runtime config the frontend needs (API URL, Supabase URL/anon key) must be set in the Vercel project’s Environment Variables so they are baked in at build.

### Auth (Supabase + backend)

- **Google OAuth:** Sign-in is required for chat. Supabase Auth with Google is used; the frontend sends the JWT in `Authorization: Bearer <token>` to `/api/chat` and session endpoints.
- **Backend verification:** The backend verifies the JWT using either Supabase JWT Signing Keys (JWKS/ES256) or a legacy HS256 secret (`SUPABASE_JWT_SECRET`). If auth is misconfigured or the token is missing/invalid/expired, the API returns **401**.
- **Redirect URLs:** Google provider and redirect URLs (e.g. `http://localhost:5173` for dev, plus production Vercel URL) must be set in Supabase Dashboard → Authentication → Providers.

### RAG pipeline and data

- **Six-stage retrieval:** Every chat query runs: (1) query expansion (entity_aliases), (2) summary-level vector search → candidate doc_ids, (3) chunk-level vector search within those docs, (4) triple lookup (rdf_triples) filtered by query terms, (5) context assembly (chunks + triples + system instruction), (6) LLM generation. The API contract is fixed: `answer`, `sources`, `triples` (arrays can be empty).
- **Hybrid candidates:** Besides summary embeddings, candidate doc_ids can come from triple-based search via the RPC `get_doc_ids_by_triple_terms`. That RPC must be created in Supabase once by running `backend/ingestion/rpc_triple_candidate_doc_ids.sql`.
- **Vector indexes:** pgvector `ivfflat` indexes on `chunks.embedding` and `chunks.summary_embedding` are required for fast retrieval. They are created by `create_indexes.py` after chunks and embeddings are populated.

### RAG pipeline speed and embedding model choice (Ollama vs OpenAI)

- **Why we switched from Ollama embeddings back to OpenAI:** The project supports both: `retrieval/embedding.py` can use `EMBED_PROVIDER=openai` or `ollama` (e.g. `qwen3-embedding:8b`). Ollama runs **locally** (HTTP to `localhost:11434`). That means (1) **no built-in concurrency** — requests are often processed one at a time or with limited parallelism; (2) **CPU or single-GPU bound** — embedding 1536-dim vectors for every query and for ingestion is heavy; (3) **timeouts** — the code uses a long timeout (e.g. 300s) because Ollama can be slow; (4) **ingestion** — re-embedding the full corpus with Ollama would take orders of magnitude longer than OpenAI’s API. OpenAI’s embedding API is built for **throughput**: batched requests, fast responses, and predictable latency. For a production-style RAG pipeline where every chat does at least one query embedding (and two vector searches), **OpenAI was chosen for speed and reliability**; Ollama remains an option for local-only or experimentation.
- **Where embeddings are used:** Query embedding (for summary + chunk search) and, in ingestion, chunk and summary embeddings. If you use Ollama for chat, the vectors in the DB must still match the model/dimensions (e.g. 1536); re-embedding with a different model requires nulling embeddings and re-running `embed_chunks.py`.

### Config and API key loading

- **Single source of truth:** All secrets and tunables should come from **`backend/.env`** and be read through **`backend/config.py`** (which uses `load_dotenv()` and `os.getenv()`). No hardcoded keys or URLs.
- **Why the “right” API keys sometimes didn’t work:** The codebase loads config in **multiple places**: `api/chat.py`, `retrieval/embedding.py`, `ingestion/embed_chunks.py`, and others each load `config.py` via `importlib` (so they get a fresh read of the module). But **when** and **from where** `.env` is loaded matters. If (1) the process was started from a **different working directory**, `load_dotenv()` in `config.py` looks for `.env` in the current working directory, not necessarily `backend/.env`; (2) **shell environment variables** were set to an old key, they can override `.env` depending on `load_dotenv(override=True)` and order of execution; (3) some code paths (e.g. `chat.py`’s `_get_query_embedding`) read `OPENAI_API_KEY` from their own import of config at **startup** — if the server was started before `.env` was updated, it keeps the old value until restart. So “we had the right API keys with credit in `.env` but it still wasn’t working” often meant the **running process was still using keys from somewhere else** (wrong .env path, stale env, or config cached at import). **Fix:** Ensure the backend is always run from `backend/` (or that every entry point explicitly loads `backend/.env` first), restart the server after changing `.env`, and avoid setting API keys in the shell when you intend to use `.env`.

### Triples and Supabase RPCs

- **What triples are used for:** `rdf_triples` holds structured facts (actor, action, target, location, timestamp, doc_id). They are used in two ways: (1) **Candidate expansion** — find doc_ids where actor/target/action match query terms (via the RPC `get_doc_ids_by_triple_terms`), then merge with summary-search candidates; (2) **Context and response** — for the top doc_ids, fetch matching triples and pass them to the LLM and return them in the API as `triples`.
- **What an RPC is in Supabase:** Supabase exposes Postgres **functions** as **RPCs** (Remote Procedure Calls). The client calls `client.rpc("function_name", { "param": value })`. The function runs **inside the database**, so you can do complex SQL (e.g. vector similarity + filters, or triple matching) in one round-trip. We never did this before, so it was new: you **define the function in SQL** (in the Supabase SQL Editor or a migration), then **call it by name** from Python. If the RPC doesn’t exist, the call fails with a clear error; the fix is to run the corresponding `.sql` script once.
- **RPCs we use:** (1) **`get_doc_ids_by_triple_terms`** — takes a list of search terms and returns distinct `doc_id`s from `rdf_triples` where actor, target, or action match (ILIKE). Required for hybrid candidate expansion. (2) **`match_chunks_summary`** — vector similarity on `chunks.summary_embedding`; returns candidate doc_ids for the coarse pass. (3) **`match_chunks_in_docs`** — vector similarity on `chunks.embedding` restricted to a list of doc_ids; returns top chunks for the fine pass. (4) **`get_entity_preset_list`** — returns entities with counts for the graph UI. All of these must be **created once** in Supabase (run the ingestion SQL scripts). **Statement timeout:** The vector RPCs can exceed Postgres’ default statement timeout; we applied `fix_chunk_search_timeout.sql` to set a 30s timeout on those functions so long-running vector searches don’t get killed mid-run.

### Ingestion and embeddings

- **Chunking and embedding:** Documents are chunked (~400 tokens, 50-token overlap); each chunk gets an embedding (and each chunk stores the document’s `paragraph_summary` embedding as `summary_embedding`). If chunks exist but embeddings are missing (NULL), retrieval returns no or poor results.
- **Diagnosing empty retrieval:** Scripts like `check_embedding_state.py` compare total chunk count vs non-NULL embedding counts. If most rows have NULL embeddings, the vector search has nothing to run on.
- **Re-embedding:** To switch embedding model, you can run `null_embeddings_for_reembed.py` to set `embedding` and `summary_embedding` to NULL, then re-run `embed_chunks.py`.

### Frontend and UX

- **Mobile-first and breakpoints:** Layout and density (header, chat vs evidence, graph vs sidebar) change by breakpoint; touch targets and tap highlights matter on mobile.
- **Modals:** Constrain height and use overscroll behavior so modals don’t break scroll or feel cramped on small screens.

---

## 3. Problems encountered and how we solved them

### 3.1 401 on `/api/chat` (or `/api/sessions`)

**Problem:** After signing in with Google, requests to `/api/chat` (or session endpoints) return 401 Unauthorized.

**Causes and fixes:**

1. **Backend not using the same Supabase project**  
   **Fix:** Use the same Supabase project for frontend Auth and backend. In backend `.env`, set `SUPABASE_JWT_SECRET` to the exact value from **Supabase Dashboard → Project Settings → API → JWT Secret** (and ensure `SUPABASE_URL` matches that project if using JWKS).
2. **Expired or wrong token**  
   **Fix:** Sign out and sign in again in the app so the frontend gets a fresh JWT from Supabase.
3. **Auth not configured on the server**  
   **Fix:** If both JWKS URL and `SUPABASE_JWT_SECRET` are missing, the backend returns 401 with a message like “Server auth not configured.” Set `SUPABASE_URL` and/or `SUPABASE_JWT_SECRET` in backend `.env`.

### 3.2 Vercel: wrong root or build

**Problem:** Deploy fails or builds the wrong directory (e.g. repo root instead of `frontend`).

**Solution:** In Vercel project settings, set **Root Directory** to `frontend`. Use **Build Command** `npm run build` (so the script in `package.json` is used) and **Output Directory** `dist`. Framework preset: **Vite**.

### 3.3 Vercel: frontend can’t reach backend or Supabase

**Problem:** Deployed app shows network errors or “invalid API” when calling the backend or Supabase.

**Solutions:**

- Set **Environment Variables** in Vercel: `VITE_API_URL` (production backend URL), `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` (at least for Production).
- Ensure the **backend allows CORS** from the Vercel origin (e.g. `https://your-app.vercel.app`). In this project, FastAPI uses `CORSMiddleware` with appropriate origins.

### 3.4 Chat returns no or irrelevant results (empty retrieval)

**Problem:** RAG answers are empty or not grounded in the corpus.

**Possible causes and fixes:**

1. **Chunks exist but embeddings are NULL**  
   **Fix:** Run `python -m ingestion.check_embedding_state` from `backend/`. If non-NULL counts are 0 or tiny, run the embedding pipeline: `embed_chunks.py` (and ensure `OPENAI_API_KEY` and `SUPABASE_DB_URL` are set). Resolve any rate-limit or API errors during embedding.
2. **RPC for triple-based candidates missing**  
   **Fix:** Run `backend/ingestion/rpc_triple_candidate_doc_ids.sql` in the Supabase SQL editor once so `get_doc_ids_by_triple_terms` exists. Otherwise the pipeline may skip or fail the triple-candidate step.
3. **Vector indexes missing**  
   **Fix:** After populating chunks and embeddings, run `create_indexes.py` so ivfflat indexes exist on `chunks.embedding` and `chunks.summary_embedding`.

### 3.5 RAG pipeline speed: Ollama embeddings too slow (switched back to OpenAI)

**Problem:** Using Ollama for embeddings (e.g. `EMBED_PROVIDER=ollama` with `qwen3-embedding:8b`) made the RAG pipeline too slow — chat felt sluggish and ingestion would have taken far too long.

**Why Ollama was slow:** Ollama runs on your machine (localhost). Embedding is compute-heavy; Ollama typically handles requests with limited concurrency and no batching like a cloud API. So each query embedding (and in ingestion, each chunk or batch) pays full latency. OpenAI’s embedding API is built for throughput and low latency. For production-style use (many queries, or one-time full corpus embedding), **we switched back to OpenAI** (`EMBED_PROVIDER=openai` or unset, with `OPENAI_API_KEY` and `OPENAI_EMBED_MODEL` in `.env`). The code still supports Ollama for local-only or experiments; just be aware of the speed tradeoff.

### 3.6 API keys with credit in .env but the app still didn’t work

**Problem:** We had the correct API keys (with balance) in `backend/.env`, but the backend still failed with auth or “invalid API key” errors.

**Cause:** The codebase wasn’t always using the most up-to-date values from `.env`. Reasons: (1) **Working directory** — if the server or script was run from the repo root (or another directory), `config.py`’s `load_dotenv()` looks for `.env` in the current working directory by default; that might not be `backend/.env`. (2) **Config loaded once at startup** — modules like `api/chat.py` load `config.py` at import time and read `OPENAI_API_KEY` then. If you changed `.env` after starting the server, the process kept the old key until restart. (3) **Stale shell environment** — if `OPENAI_API_KEY` (or similar) was set in the shell to an old or empty value, it could be used instead of or before `.env` depending on load order.

**Fix:** (1) Run the backend from `backend/` so `backend/.env` is the one found, or ensure every entry point explicitly loads `Path(backend)/.env` before importing config. (2) Restart the FastAPI server (and any ingestion scripts) after changing `.env`. (3) Don’t rely on shell-exported keys when you mean to use `.env`; prefer a single source of truth (`backend/.env`) and document it in the README.

### 3.7 Triples and Supabase RPCs (never done RPCs before)

**Problem:** The RAG pipeline needs to (a) get candidate doc_ids from `rdf_triples` by matching actor/target/action to query terms, and (b) run vector similarity search in the DB. Doing that efficiently from the app meant calling **database functions** (RPCs) instead of hand-written queries in Python. We hadn’t used Supabase RPCs before.

**What we did:** (1) **Define the function in SQL** — e.g. `get_doc_ids_by_triple_terms(search_terms text[], max_doc_ids int)` in `rpc_triple_candidate_doc_ids.sql` — and run it once in the Supabase SQL Editor. (2) **Call it from Python** — `client.rpc("get_doc_ids_by_triple_terms", {"search_terms": terms, "max_doc_ids": 25})`. (3) **Handle missing RPC** — if the RPC wasn’t created yet, the call fails; the pipeline catches the exception and falls back to summary-only candidates, and the docs tell you to run the SQL script. (4) **Statement timeout** — the vector RPCs (`match_chunks_summary`, `match_chunks_in_docs`) can run long; we ran `fix_chunk_search_timeout.sql` to set `statement_timeout = '30s'` on those functions so Postgres doesn’t kill them with the default 8s timeout. **Takeaway:** RPCs are just Postgres functions you create with SQL and invoke by name from the client; list all required RPCs and their scripts in the README/PROGRESS so they’re not forgotten in a new environment.

### 3.8 UI broken or cramped on mobile

**Problem:** Layout, buttons, or modals are unusable or ugly on small screens.

**Solution (from Session 2):** Use responsive layout and components:

- Stack main content vertically on small viewports; side-by-side from `md` up.
- Use icon-only controls on mobile and full labels on larger screens.
- Ensure touch targets ≥ 44px; limit snippet length and truncate long IDs in cards.
- Modals: `max-h-[90vh]`, safe margins, and `overscroll-contain`.
- Use viewport and safe-area settings (`viewport-fit=cover`, `pb-safe`) for notched devices and home indicators.

### 3.9 Deleting and recreating the Vercel project

**Problem:** Need to “start over” on Vercel (e.g. new project, same repo).

**Solution:** Delete the project (Dashboard → Settings → Delete Project, or `vercel remove <name> --yes`). Then at vercel.com/new, import the same repo, set root to `frontend`, add env vars again, and re-add the custom domain if used. Note: Deleting and recreating to game first-24-hour metrics (Product Hunt, hackathons) is often against program rules.

### 3.10 POST /api/sessions 500 — Supabase Python client: insert().select() not supported

**Problem:** After implementing chat sessions, the first message in a new chat triggered `POST /api/sessions`, which returned 500 Internal Server Error. The handler was catching all exceptions and returning a generic “Failed to create session” with no traceback or detail.

**Steps to find the cause:** (1) Add `traceback.print_exc()` and `detail=f"Failed to create session: {e!s}"` in the `create_session` except block so the server logs and the HTTP response show the real error. (2) Restart the backend (or use `uvicorn ... --reload` so changes apply), reproduce the 500, then read the terminal and/or response body.

**Actual error:** `AttributeError: 'SyncQueryRequestBuilder' object has no attribute 'select'`. The code was chaining `.select("id, title, created_at, updated_at")` after `.insert({...})`. In the Supabase Python client version in use, the object returned by `.insert()` does not have a `.select()` method, so the chain is invalid.

**Fix:** Do not rely on insert-return. (1) Generate the session id in the app with `uuid4()`. (2) Generate `created_at` and `updated_at` with `datetime.now(timezone.utc).isoformat()`. (3) Insert the row with all five columns (`id`, `user_id`, `title`, `created_at`, `updated_at`) and call `.execute()` only. (4) Return the session dict you already have (no second query or `.select()`). The API response shape is unchanged; only the implementation no longer depends on the client’s insert-return behavior.

**Takeaway:** When a 500 has no visible cause, surface the exception (traceback + optional safe message in the response) first. Supabase (and other) client APIs can differ by version; if a chained method doesn’t exist, use a pattern that doesn’t need it (e.g. generate IDs/timestamps in the app and return them after insert).

---

## 4. Conceptual summary — apply in the future

### 4.1 Deployment and environment

- **Separate “where the app lives” from “where it’s built”.** For monorepos or frontend-in-subfolder projects, always set the **root directory** on the host (Vercel, Netlify, etc.) so build and env are evaluated in that folder.
- **Prefer `npm run build` over calling the bundler directly.** The script in `package.json` is the contract; the host runs it with the right PATH and environment.
- **Frontend env at build time:** For Vite (and similar), only `VITE_*` (or the framework’s prefix) is exposed to the client. Document every such variable and set them in the deployment UI; never commit secrets.
- **Split frontend and backend hosting:** When the API is separate (e.g. FastAPI), deploy it elsewhere and point the frontend’s API base URL to that host. Configure CORS on the backend for the frontend’s production (and preview) origins.

### 4.2 Config and API keys: one source of truth

- **Load .env from a fixed path.** If config is read from “current directory” or “first .env found,” changing the run directory (e.g. `python -m api.main` from repo root vs `backend/`) can make the process use a different or missing `.env`. Prefer explicitly loading `backend/.env` (or a single env file) in one place (e.g. `config.py`) and running from a documented working directory (or passing the env path).
- **Restart after changing secrets.** Many servers and scripts read env/config at startup. After updating API keys in `.env`, restart the backend and any long-running scripts so they pick up the new values.
- **Avoid “right key in .env but app still fails.”** When that happens, the app is usually reading from somewhere else: wrong cwd, stale process, or shell-exported vars. Fix: single .env path, restart, and document how config is loaded.

### 4.3 Auth across frontend and backend

- **One Supabase project for Auth and backend verification.** Use the same JWT secret (or JWKS) so tokens issued by Supabase Auth validate on the backend. Document the exact env vars (e.g. `SUPABASE_JWT_SECRET`) and where to copy them from (Dashboard → Project Settings → API).
- **401 debugging checklist:** (1) Same project and JWT secret on backend, (2) Valid/current token (re-sign-in if needed), (3) Redirect URLs and provider enabled in Supabase for the environment (dev/prod).

### 4.4 RAG and vector search

- **Retrieval depends on populated vectors and indexes.** If the app has a “no results” or “empty context” symptom, check in order: (1) Are rows in the vector table actually filled (non-NULL)? (2) Are indexes created after data load? (3) Are any required DB objects (RPCs, functions) created by migration/setup scripts?
- **Document one-time setup steps.** List every SQL script or ingestion step that must run once (schema, RPCs, indexes). Put them in a single place (e.g. README or PROGRESS.md) so new environments don’t miss a step.
- **Contract for RAG API:** Decide a fixed response shape (e.g. `answer`, `sources`, `triples`) and always return it (use empty arrays when there are no sources/triples). The frontend and any clients can rely on that shape.
- **Embedding provider tradeoff:** Local embedders (e.g. Ollama) avoid API cost but are often slow and single-request; cloud embedders (e.g. OpenAI) give speed and throughput. For production RAG (many queries or full-corpus ingestion), prefer a fast, batched API unless you explicitly optimize for local-only or cost over latency.
- **Supabase RPCs are Postgres functions.** You create them in SQL (Supabase SQL Editor or migration), then call them by name from the client. They run inside the DB (one round-trip, can do vector search + filters). Treat RPCs as **required one-time setup**: list each RPC and its `.sql` file, and set statement timeouts on heavy functions so they don’t hit the default Postgres timeout.

### 4.5 Responsive and mobile UX

- **Layout by breakpoint:** Define breakpoints (e.g. Tailwind `md:`) and switch from stacked to side-by-side, and from icon-only to labeled controls, so the same app works on phone and desktop.
- **Touch and modals:** Use minimum touch target size; constrain modal height and handle overscroll so the rest of the page doesn’t scroll behind the modal on mobile.
- **Safe areas and viewport:** Use viewport and safe-area utilities for notches and home indicators so content isn’t hidden or cramped.

### 4.6 Operational and product rules

- **Don’t assume “first 24 hours” resets.** If a platform (Product Hunt, hackathon, startup program) uses time-based metrics, check their rules before deleting and redeploying to reset; many prohibit relaunching the same product.
- **Keep a progress doc.** A file like PROGRESS.md that tracks phases, required SQL/scripts, and common pitfalls (e.g. 401, NULL embeddings, missing RPC) saves time for you and anyone else setting up the project later.

### 4.7 Debugging 500s and client API differences

- **Always surface the real error for 500s.** Catch exceptions in handlers but log the traceback (e.g. `traceback.print_exc()`) and optionally include a safe part of the message in the response (e.g. `detail=f"Failed to create session: {e!s}"`). Otherwise you waste time guessing (wrong table? env? permissions?) when the traceback would tell you immediately.
- **Client libraries can differ by version.** If the docs or another project show a chain like `.insert().select().execute()` and your client raises “object has no attribute 'select'”, that API may not exist in your version. Prefer patterns that don’t depend on it: e.g. generate IDs and timestamps in the app, insert once, and return the data you already have.
- **404 after OAuth redirect:** If the “resource” that 404s is the main document (the redirect URL), the frontend might not be running there or the redirect URL is wrong. If the 404 is from a different host (e.g. `DEPLOYMENT_NOT_FOUND` with a platform-specific id), that’s the host saying “no deployment at this URL” (e.g. Vercel when the frontend isn’t deployed yet), not Supabase or your backend.

---

This document reflects the conversation history in the referenced agent transcripts, the project’s README and docs (BACKEND_PLAN.md, PROGRESS.md), and the codebase (backend API/auth/ingestion/retrieval, frontend structure and env usage). Update it as you hit new problems and solutions so it stays a useful learning journal.
