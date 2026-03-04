# Deploying with Llama 3.2 / 3.3

This guide explains how to switch the chat from Claude to Llama 3.2 or 3.3 so it is used in development and in production.

---

## Overview

- Chat uses an OpenAI-compatible API. Set `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_API_KEY` for your provider (e.g. OpenRouter or Groq for Llama 3.2/3.3).
- No code changes are required; only environment variables.

---

## Option A: Groq (recommended for speed and free tier)

Groq hosts Llama 3.2 and 3.3 with very low latency. Free tier available.

### Step 1: Get a Groq API key

1. Go to [https://console.groq.com](https://console.groq.com).
2. Sign up or log in.
3. Open **API Keys** (in the left sidebar or under your account).
4. Click **Create API Key**. Name it (e.g. `RAGforEFN`) and copy the key (starts with `gsk_`). Store it securely; you may not see it again.

### Step 2: Choose a Llama model on Groq

Groq exposes models via an OpenAI-compatible API. Use one of these **model IDs** in `LLM_MODEL`:

| Model ID (use as `LLM_MODEL`) | Description |
|-------------------------------|-------------|
| `llama-3.3-70b-versatile` | Llama 3.3 70B, strong quality (recommended). |
| `llama-3.2-90b-vision-preview` | Llama 3.2 90B (if available on your plan). |
| `llama-3.2-3b-preview` | Smaller, faster, lower cost. |
| `llama-3.1-8b-instant` | Fast, smaller. |

Check [Groq’s model list](https://console.groq.com/docs/models) for the latest IDs; they may add or rename models.

### Step 3: Configure your environment

**Local development (backend)**

1. Open or create `backend/.env`.
2. Set or add these lines (replace the key with your Groq API key):

```env
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile
LLM_API_KEY=gsk_your_groq_api_key_here
```

3. Restart the backend (e.g. stop and run `uvicorn` again).

**Production / deployed backend**

Set the same variables in your hosting provider’s environment (see [Production deployment](#production-deployment) below). Do **not** commit `.env` or real keys to git.

### Step 4: Verify

1. Start the backend from `backend/` (e.g. `uvicorn api.main:app --reload`).
2. In the app, send a chat message that should trigger RAG (e.g. a question about the documents).
3. You should get an answer; the model behind it is now Llama (Groq), not Claude.
4. If you see an error about `LLM_BASE_URL` or `LLM_MODEL`, double-check that `backend/.env` is loaded (and that you restarted the process after editing `.env`).

---

## Option B: OpenRouter (one key, many models)

OpenRouter lets you call many models (including Llama) with a single API key and OpenAI-compatible endpoint. **For a full step-by-step guide with the “why” behind each step, see [OPENROUTER_SETUP.md](OPENROUTER_SETUP.md).**

### Step 1: Get an OpenRouter API key

1. Go to [https://openrouter.ai](https://openrouter.ai).
2. Sign up or log in.
3. Open **Keys** and create an API key. Copy it (often starts with `sk-or-v1-`).

### Step 2: Choose a Llama model on OpenRouter

OpenRouter uses **slash-style** model IDs. Examples:

| Model ID (use as `LLM_MODEL`) | Description |
|-------------------------------|-------------|
| `meta-llama/llama-3.3-70b-instruct` | Llama 3.3 70B. |
| `meta-llama/llama-3.2-90b-vision-instruct` | Llama 3.2 90B. |
| `meta-llama/llama-3.2-3b-instruct` | Smaller, cheaper. |

Browse [OpenRouter models](https://openrouter.ai/models) and copy the exact model ID.

### Step 3: Configure your environment

In `backend/.env` (or your production env):

```env
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=meta-llama/llama-3.3-70b-instruct
LLM_API_KEY=sk-or-v1-your_openrouter_key_here
```

Restart the backend and test chat as in Step 4 above.

---

## Production deployment

Wherever the **backend** runs (VPS, Railway, Render, Fly.io, Docker, etc.), set the same variables so the deployed app uses Llama.

### Example: Railway / Render / similar

1. Open your project → **Variables** (or **Environment**).
2. Add or edit:
   - `LLM_BASE_URL` = `https://api.groq.com/openai/v1` (Groq) or `https://openrouter.ai/api/v1` (OpenRouter)
   - `LLM_MODEL` = e.g. `llama-3.3-70b-versatile` (Groq) or `meta-llama/llama-3.3-70b-instruct` (OpenRouter)
   - `LLM_API_KEY` = your Groq or OpenRouter API key
3. Redeploy so the new env vars are picked up.

### Example: Docker

Pass env in `docker run` or in a `.env` file used by Compose:

```bash
docker run -e LLM_BASE_URL=https://api.groq.com/openai/v1 \
  -e LLM_MODEL=llama-3.3-70b-versatile \
  -e LLM_API_KEY=gsk_... \
  ...
```

Or in `docker-compose.yml` under the backend service:

```yaml
environment:
  - LLM_BASE_URL=https://api.groq.com/openai/v1
  - LLM_MODEL=llama-3.3-70b-versatile
  - LLM_API_KEY=${LLM_API_KEY}
```

Use secrets or a vault for `LLM_API_KEY` in production; do not hardcode.

### Example: Manual server (systemd / shell)

Export before starting the app, or put in a file loaded by your process (e.g. `backend/.env` on the server):

```bash
export LLM_BASE_URL=https://api.groq.com/openai/v1
export LLM_MODEL=llama-3.3-70b-versatile
export LLM_API_KEY=gsk_your_key
```

---

## Checklist summary

- [ ] Get API key from Groq or OpenRouter.
- [ ] Set `LLM_BASE_URL` (Groq: `https://api.groq.com/openai/v1`, OpenRouter: `https://openrouter.ai/api/v1`).
- [ ] Set `LLM_MODEL` to the exact model ID (e.g. `llama-3.3-70b-versatile` for Groq).
- [ ] Set `LLM_API_KEY` to your key.
- [ ] Restart backend (or redeploy in production).
- [ ] Test a chat request to confirm Llama is used.
