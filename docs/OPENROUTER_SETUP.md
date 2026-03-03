# OpenRouter setup guide

Step-by-step setup for using OpenRouter with Llama 3.2/3.3 in this app, and why each part works the way it does.

---

## Why OpenRouter here?

- **One API key** for many models (Llama, Claude, Mistral, etc.); you can switch models by changing one env var.
- **Lower cost per token** for Llama 3.3 70B than going directly to Groq paid, so your budget (e.g. $4) supports more chats and more users.
- **OpenAI-compatible API** — the same `openai` library and request format we already use for the “openai_compatible” path works with OpenRouter; no extra code.

The app doesn’t talk to OpenRouter’s website; it sends HTTP requests to OpenRouter’s API. Your backend only needs the right URL, model ID, and API key.

---

## Step 1: Create an OpenRouter account and get an API key

**What to do**

1. Go to **[https://openrouter.ai](https://openrouter.ai)**.
2. Sign up or log in (e.g. Google / GitHub).
3. Open **Keys** (in the dashboard or under your profile).
4. Click **Create Key**. Give it a name (e.g. `RAGforEFN`), create it, and **copy the key** (often starts with `sk-or-v1-`). Store it somewhere safe; you may not see it again.

**Why**

The key proves requests are from you. OpenRouter uses it to track usage and, if you add credits, to charge that account. Every request from your backend must include this key in the `Authorization` header; our code does that via `LLM_API_KEY`.

---

## Step 2: Add credits (for paid models like Llama 3.3 70B)

**What to do**

1. In the OpenRouter dashboard, go to **Credits** or **Billing**.
2. Add credits (e.g. **$4** or whatever you plan to spend). You can use a card or other payment method they support.
3. Your balance will show in the dashboard. Usage is deducted from this balance.

**Why**

OpenRouter’s **free** models have tight limits (e.g. 20 req/min, 200 req/day). To support “a lot of users” with Llama 3.2/3.3 70B you use **paid** model IDs (no `:free` suffix). Paid models consume credits per token; a few dollars is enough for hundreds or thousands of chats depending on model and length.

---

## Step 3: Pick the exact model ID

**What to do**

1. Go to **[https://openrouter.ai/models](https://openrouter.ai/models)**.
2. Search or browse for **Llama 3.3** or **Llama 3.2**.
3. Open the model you want (e.g. **Llama 3.3 70B Instruct**).
4. Copy the **model ID** exactly as shown (e.g. `meta-llama/llama-3.3-70b-instruct`). You’ll paste this into `LLM_MODEL`.

**Why**

OpenRouter uses **slash IDs** like `provider/model-name`. The backend sends this string in the `model` field of every request; OpenRouter uses it to route to the right provider and model. If you mistype the ID, requests can fail or hit a different model.

---

## Step 4: Set environment variables (backend)

**What to do**

1. Open or create **`backend/.env`** (in the same folder as `config.py`).
2. Add or set these lines. Use **your** OpenRouter API key and the model ID you copied:

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=meta-llama/llama-3.3-70b-instruct
LLM_API_KEY=sk-or-v1-paste-your-key-here
```

3. Save the file. **Do not** commit `.env` or your real key to git (`.env` should be in `.gitignore`).

**Why each variable**

| Variable | Value | Why |
|----------|--------|-----|
| `LLM_PROVIDER` | `openai_compatible` | Tells the app to use the generic “OpenAI-compatible” path in `llm_generation.py` instead of calling Anthropic. That path uses `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_API_KEY`. |
| `LLM_BASE_URL` | `https://openrouter.ai/api/v1` | Root URL of OpenRouter’s API. The `openai` client sends requests here (e.g. `POST .../chat/completions`). Same format as OpenAI, so one code path fits. |
| `LLM_MODEL` | `meta-llama/llama-3.3-70b-instruct` | Exact model ID OpenRouter uses to route and bill. Must match a model on their site. |
| `LLM_API_KEY` | `sk-or-v1-...` | Your OpenRouter key. The client sends it as `Authorization: Bearer <key>` so OpenRouter knows who you are and which credits to use. |

The backend loads these from `config.py`, which reads `os.getenv(...)`. So the running process must see these env vars (from `.env` when you run locally, or from your host’s env in production).

---

## Step 5: Restart the backend and test

**What to do**

1. Stop the backend if it’s running (Ctrl+C in the terminal where you run uvicorn).
2. Start it again from the `backend/` directory, e.g.:

   ```bash
   cd backend
   uvicorn api.main:app --reload
   ```

3. In your app, send a **chat message** that should trigger RAG (e.g. a question about the documents).
4. You should get an answer. If you see an error, check the next section.

**Why restart**

The backend reads env vars when it starts. Changing `.env` doesn’t affect an already-running process. Restarting picks up the new `LLM_*` values so the next chat request uses OpenRouter and Llama.

---

## Step 6: If something goes wrong

**“LLM_BASE_URL or LLM_MODEL is not set”**

- Ensure `backend/.env` exists and has `LLM_PROVIDER=openai_compatible`, `LLM_BASE_URL=...`, and `LLM_MODEL=...` with no typos.
- Ensure you restarted the backend after editing `.env`.

**401 Unauthorized or invalid API key**

- Check that `LLM_API_KEY` is the full key from OpenRouter (starts with `sk-or-v1-`), with no extra spaces or quotes in `.env`.
- On OpenRouter, confirm the key is still active and not revoked.

**Out of credits / 402 or rate limit**

- Add more credits in the OpenRouter dashboard, or switch to a free model (e.g. a `:free` variant) to test — though free models have low daily limits.

**Wrong or weird answers**

- Confirm `LLM_MODEL` matches the model you want (e.g. `meta-llama/llama-3.3-70b-instruct`). You can try another model ID from [openrouter.ai/models](https://openrouter.ai/models) and restart.

---

## Summary checklist

- [ ] Account at [openrouter.ai](https://openrouter.ai)
- [ ] API key created and copied
- [ ] Credits added (for paid Llama 3.2/3.3)
- [ ] Model ID copied from [openrouter.ai/models](https://openrouter.ai/models)
- [ ] `backend/.env` has `LLM_PROVIDER=openai_compatible`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`
- [ ] Backend restarted
- [ ] One chat request sent and answered

After this, all chat requests that go through your backend will use OpenRouter and the Llama model you chose until you change the env vars or switch back to `LLM_PROVIDER=anthropic`.
