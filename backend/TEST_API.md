# Step-by-step: Testing the Phase 5 API

Do these in order. Use two windows: one terminal for the server, one browser (or a second terminal) for requests.

---

## What the response codes mean

| Code | Name | Meaning |
|------|------|--------|
| **200** | OK | The request worked. The response body has the data you asked for (e.g. JSON with stats, document, or chat answer). |
| **404** | Not Found | The resource doesn’t exist. For this API: you used a `doc_id` that isn’t in the database (e.g. `test-nonexistent-123`). So “404” here = “no such document.” |
| **422** | Unprocessable Entity | The request was valid HTTP but the parameters are wrong or missing. For this API: usually **missing or invalid query parameter** (e.g. you called `/api/chat` without `q`, or sent something the server can’t accept). Fix the parameters and try again. |
| **500** | Internal Server Error | Something broke on the server (bug, missing config, or DB/API error). Check the server terminal for a traceback; fix the cause before retrying. |

**In short:**  
- **200** = success.  
- **404** = that document (or resource) doesn’t exist.  
- **422** = bad or missing input (e.g. empty `q` on chat).  
- **500** = server error; look at the server logs.

---

## Step 1: Start the server

1. Open a terminal (PowerShell or Command Prompt).
2. Go to the backend folder:
   ```powershell
   cd C:\Users\aiden\Desktop\Stuff\RAGforEFN\backend
   ```
3. If you use a virtual environment, activate it (e.g. `.\venv\Scripts\Activate.ps1`).
4. Start the API:
   ```powershell
   python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
   ```
5. Leave this terminal open. You should see something like:
   ```
   INFO:     Uvicorn running on http://0.0.0.0:8000
   INFO:     Application startup complete.
   ```

---

## Step 2: Open the API docs in your browser

1. Open a browser (Chrome, Edge, Firefox, etc.).
2. In the address bar go to:
   ```
   http://127.0.0.1:8000/docs
   ```
3. You should see the **Swagger UI** page with a list of endpoints (GET /, GET /api/chat, GET /api/document/..., etc.).

---

## Step 3: Test the root and health endpoints

1. On the Swagger page, find **GET /**.
2. Click it, then click **"Try it out"**, then **"Execute"**.
3. Check the response: status **200** and body like `{"status":"ok","service":"RAG API"}`.
4. Do the same for **GET /health**: click it → Try it out → Execute. Expect **200** and `{"status":"ok"}`.

---

## Step 4: Test GET /api/stats

1. Find **GET /api/stats** in the list.
2. Click it → **Try it out** → **Execute**.
3. Check: status **200**, and the response body has four numbers:
   - `document_count`
   - `triple_count`
   - `chunk_count`
   - `actor_count`  
   (Exact values depend on your database; just confirm all four keys exist.)

---

## Step 5: Test GET /api/tag-clusters

1. Find **GET /api/tag-clusters**.
2. Click it → **Try it out** → **Execute**.
3. Check: status **200**, and the response is a **JSON array**.  
   It may be empty `[]` or have up to 30 items like `{"id":"...","label":"...","count":...}`. Both are fine.

---

## Step 6: Test GET /api/document/{doc_id} (invalid first)

1. Find **GET /api/document/{doc_id}**.
2. Click it → **Try it out**.
3. In the **doc_id** box, type a fake ID: `test-nonexistent-123`.
4. Click **Execute**.
5. Check: status **404** and a message like "Document not found". That’s correct.

---

## Step 7: Test GET /api/document/{doc_id}/text (invalid first)

1. Find **GET /api/document/{doc_id}/text**.
2. Click it → **Try it out** → enter the same fake `doc_id`: `test-nonexistent-123` → **Execute**.
3. Check: status **404**.

---

## Step 8: Test GET /api/search (invalid then real)

1. Find **GET /api/search**.
2. Click it → **Try it out**.
3. **Invalid:** Leave `q` empty or set to a single space, Execute. Expect **200** with body `[]` (empty array), or **422** if the API rejects empty. Note which you get.
4. **Real:** Set `q` to a term that should exist in your corpus (e.g. `epstein`, `jeffrey`, or a name from your documents). Execute.
5. Check: status **200** and a **JSON array**. If your corpus has entity_aliases and triples, you should see at least one entry like `{"canonical_name":"...","count":<number>}`. Verify each item has `canonical_name` and `count`, and counts are non‑negative.

---

## Step 9: Test GET /api/chat (main RAG endpoint) — and get a real doc_id

1. Find **GET /api/chat**.
2. Click it → **Try it out**.
3. In the **q** box type a real question, e.g. `Who is mentioned in these documents?` or `What do these documents say about flights?`
4. Click **Execute** and wait 10–30 seconds.
5. Check:
   - Status **200**.
   - Response body has exactly three keys: **`answer`**, **`sources`**, **`triples`**.
   - `answer` is a non‑empty string (real prose from Claude).
   - `sources` is an array. If non‑empty, each item has `doc_id`, `one_sentence_summary`, `category`, `date_range_earliest`, `date_range_latest` (some can be null). **Pick one `doc_id` from `sources[0]` (or any source) and keep it for Steps 10–11.**
   - `triples` is an array; each item has `actor`, `action`, `target`, `timestamp`, `location`, `doc_id`. If present, spot‑check that at least one triple’s `doc_id` appears in `sources`.

---

## Step 10: Test GET /api/chat with empty q (expect 422)

1. Still on **GET /api/chat**, click **Try it out** again.
2. **Clear** the **q** box so it’s empty (or clear the query parameter).
3. Click **Execute**.
4. Check: status **422** (Unprocessable Entity). The API correctly requires a query.

---

## Step 11: Real doc_id — GET /api/document/{doc_id}

1. Use the **real `doc_id`** you copied from the chat response in Step 9 (e.g. from `sources[0].doc_id`). If chat returned no sources, use **GET /api/stats** to confirm `document_count` > 0, then get a real doc_id from your database or skip this step.
2. Find **GET /api/document/{doc_id}** → **Try it out** → paste that `doc_id` → **Execute**.
3. Check: status **200**. Response must have: `doc_id`, `one_sentence_summary`, `category`, `date_range_earliest`, `date_range_latest`. At least `doc_id` should match what you sent; the others can be strings or null.

---

## Step 12: Real doc_id — GET /api/document/{doc_id}/text

1. Use the **same real `doc_id`** as in Step 11.
2. Find **GET /api/document/{doc_id}/text** → **Try it out** → paste that `doc_id` → **Execute**.
3. Check: status **200**. Response must be `{"full_text":"..."}` and `full_text` should be a non‑empty string (the document body). If the source doc has no text, it may be `""`; that’s still valid.

---

## Step 13: Real-data check — GET /api/stats

1. Open **GET /api/stats** → **Try it out** → **Execute**.
2. Check: status **200**. All four keys present: `document_count`, `triple_count`, `chunk_count`, `actor_count`.
3. **Sanity:** If your database is populated, `document_count` and `chunk_count` should be > 0. If you ran chat successfully, `triple_count` and `actor_count` should typically be > 0. If any are 0, confirm that matches your current data.

---

## Step 14: Real-data check — GET /api/tag-clusters

1. Open **GET /api/tag-clusters** → **Try it out** → **Execute**.
2. Check: status **200** and response is a JSON array.
3. **Sanity:** If your `rdf_triples` table has non‑null `top_cluster_ids`, the array should have up to 30 items. Each item: `id`, `label`, `count` (all present; `count` ≥ 0). If the array is empty, that’s OK if your data has no cluster IDs.

---

## Step 15: Second chat question (optional consistency check)

1. **GET /api/chat** → **Try it out** → use a **different** question, e.g. `Summarize the main topics in these documents.`
2. Execute and wait for **200**.
3. Check again: `answer`, `sources`, `triples` all present; `answer` is non‑empty and different from the first run. Confirms the pipeline isn’t cached to a single response.

---

## Done

If all steps match the expected status codes and response shapes (including real doc_id and real search/chat), Phase 5 is working correctly. Stop the server with **Ctrl+C** in the server terminal.
