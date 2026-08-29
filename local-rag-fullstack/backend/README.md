# Cloud RAG Assistant (Gemini + Pinecone)

A production-oriented RAG pipeline using hosted APIs instead of local models —
Gemini for embeddings/generation, Pinecone for vector storage.

This is the cloud counterpart to the fully-local (Ollama + ChromaDB) version.
Same architecture, different backends: no local GPU/CPU inference bottleneck,
scales beyond a single machine, and uses a real hosted vector DB.

## Architecture

```
Documents (PDF/txt) → Chunk → Embed (Gemini gemini-embedding-001) → Store (Pinecone)
                                                                        ↓
User Query → Embed → Vector Search (Pinecone) → Top-K Chunks → Prompt → Gemini → Answer
```

## Setup

1. **Get API keys:**
   - Gemini: https://aistudio.google.com/apikey
   - Pinecone: https://www.pinecone.io (free Starter tier)

2. **Create your `.env` file:**
   Copy `.env.example` to `.env` and fill in:
   ```
   GEMINI_API_KEY=your_actual_key
   PINECONE_API_KEY=your_actual_key
   ALLOWED_ORIGINS=http://localhost:5173
   JWT_SECRET=<generate one — see below>
   ```
   Generate a real JWT secret (never use the placeholder value):
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   `.env` is gitignored — never commit real keys/secrets.

3. **Set up a virtual environment and install dependencies:**
   ```bash
   python -m venv .venv
   .venv\Scripts\Activate.ps1        # Windows
   pip install -r requirements.txt
   ```

4. **Run the API:**
   ```bash
   uvicorn api:app --reload --port 8000
   ```
   The database (`data/app.db`) is created automatically on first run —
   no separate document folder to pre-populate anymore. Documents are
   uploaded per-user through the app itself.

5. **Create an account and start using it** — either through the React
   frontend's signup screen, or directly:
   ```bash
   curl -X POST http://localhost:8000/auth/signup \
     -H "Content-Type: application/json" \
     -d "{\"username\": \"you\", \"password\": \"a-real-password\"}"
   ```
   This returns a JWT token — use it as `Authorization: Bearer <token>`
   on every other request (the frontend does this automatically once
   you log in through the UI).

## Multi-tenancy (per-user isolation)

Each user's data is fully isolated from every other user's:

- **Documents**: stored in `data/raw/<user_id>/`, one folder per user
- **Vector search**: each user gets their own **Pinecone namespace**
  within the same index — a query in one namespace never returns
  another namespace's vectors (this is a Pinecone-native guarantee)
- **Keyword search (BM25)**: separate store file per user
  (`data/bm25_stores/<user_id>.json`)
- **Chat history**: `conversations` and `messages` tables are scoped by
  `user_id` — a user can have multiple conversations (like ChatGPT's
  chat list), and can never see another user's conversations
- **Semantic cache**: cache keys are scoped by `user_id`, so one user's
  cached answer never leaks to another user asking a similar question

## Project Structure

- `src/loader.py` — loads and chunks documents (unchanged from local version)
- `src/embed.py` — embeds chunks via Gemini, upserts into Pinecone
- `src/retrieve.py` — retrieves top-k relevant chunks from Pinecone
- `src/generate.py` — builds the grounded prompt and calls Gemini (streaming + non-streaming)
- `src/config.py` — all settings (models, index name, chunk size) in one place
- `app.py` — Streamlit chat interface with live token streaming
- `.env` — your API keys (never commit this)

## Config

Edit `src/config.py` to change:
- Gemini model (`GEMINI_LLM_MODEL`, `GEMINI_EMBED_MODEL`)
- Pinecone index name
- Chunk size / overlap
- Number of chunks retrieved per query (`TOP_K`)

## RAG architecture: hybrid search + re-ranking

Retrieval is no longer vector-search-only. The pipeline now:
1. Runs vector search (Pinecone) AND keyword search (BM25) in parallel,
   each returning a candidate pool
2. Deduplicates the combined candidates
3. Re-ranks them with a cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`,
   local — no extra API cost) for more accurate final ordering
4. Returns the top-k re-ranked chunks to the LLM

Why: vector search alone can miss exact-term matches (names, codes) that
don't embed distinctively; BM25 alone misses paraphrased/semantic matches.
Combining both and re-ranking is the standard second-stage refinement in
production retrieval systems — see `src/bm25_index.py`, `src/reranker.py`,
and the updated `src/retrieve.py`.

## Document upload (incremental ingestion)

`POST /ingest` accepts a file upload (PDF, TXT, or MD) and adds it to the
index WITHOUT wiping existing data — unlike running `embed.py` directly,
which does a full rebuild. This is what the frontend's upload button calls.

```bash
curl -X POST http://localhost:8000/ingest \
  -H "X-API-Key: your_key" \
  -F "file=@/path/to/document.pdf"
```

See `src/ingest.py` for the incremental logic (embeds + upserts just the
new document's chunks into both Pinecone and the BM25 index).

## Production concepts implemented

Beyond the core RAG pipeline (embeddings, vector search, chunking, RAG,
context window, streaming, evals), this version adds:

- **Semantic cache** (`src/cache.py`) — repeated or paraphrased questions
  skip the API call entirely (exact-match + embedding-similarity cache,
  in-memory, 1hr TTL). Cuts cost and latency on repeat queries.
- **Guardrails** (`src/guardrails.py`) — basic prompt-injection detection
  on both the user's query AND retrieved document content (a real RAG
  attack vector: a document could contain hidden instructions). Pattern-based,
  not a full moderation system — documented limitation, not a complete solution.
- **Token cost tracking** (`src/cost_tracker.py`) — every query logs real
  input/output token counts (from Gemini's `usage_metadata`) and an estimated
  cost to `logs/token_usage.csv`. Pricing constants are placeholders — verify
  against ai.google.dev/pricing before relying on them.
- **Retry with exponential backoff** (`src/utils.py`) — API calls to Gemini
  retry up to 3 times on failure (1s, 2s, 4s backoff) instead of crashing
  on a transient network blip or rate limit.
- **Structured logging** (`src/utils.py`) — every query, cache hit, guardrail
  block, and error is logged to `logs/app.log` with timestamps.

Check current usage any time:
```bash
python src/cost_tracker.py
```

## Two ways to run this

**A) Streamlit (quick demo UI):**
```bash
streamlit run app.py
```

**B) FastAPI backend (the real service layer):**
```bash
uvicorn api:app --reload --port 8000
```
Interactive docs at `http://localhost:8000/docs`. This is what a real
frontend (web, mobile, another service) would call over HTTP — Streamlit
is a convenient UI for demos, not the production interface.

**C) Docker (packages the FastAPI backend):**
```bash
docker compose up --build
```
Runs the API at `http://localhost:8000`, with `data/` and `logs/` persisted
via volume mounts so your database and documents survive container restarts.

## Backend + database concepts implemented

- **REST API** (`api.py`) — `POST /query`, `GET /history/{session_id}`,
  `GET /usage`, `GET /health`, with auto-generated OpenAPI docs
- **Request validation** — Pydantic models on every endpoint (`QueryRequest`
  enforces query length, valid `top_k` range, etc. — malformed input is
  rejected before it reaches the pipeline)
- **Async / non-blocking** — the RAG pipeline (synchronous, blocking network
  calls) runs via `asyncio.to_thread()` so it doesn't block FastAPI's event
  loop; multiple requests can be in flight concurrently
- **Authentication** (`src/auth.py`) — API key required via `X-API-Key`
  header, set in `.env` as `APP_API_KEY`
- **Rate limiting** (`src/rate_limiter.py`) — 20 requests/60s per client IP,
  in-memory sliding window
- **SQLite database** (`src/database.py`) — three tables: `sessions`,
  `messages` (persistent chat history, survives restarts — unlike
  Streamlit's session-only history), and `query_logs` (structured record
  of every query: sources, latency, cache hits, guardrail blocks)
- **Containerization** (`Dockerfile`, `docker-compose.yml`) — the whole
  API packages into one portable container with persistent volumes

## Known limitations (honest, not hidden)

- BM25 index is a local JSON file + in-memory rebuild on each app start —
  fine at this corpus scale (dozens to low hundreds of chunks), but a
  large corpus would need a real search engine (Elasticsearch/OpenSearch).
- The cross-encoder re-ranker downloads its model (~80MB) from HuggingFace
  on first use and caches it locally — expect a one-time delay the first
  time you run a query after adding this feature.
- If you already had documents indexed before adding hybrid search, run
  `python src/embed.py` once more to rebuild the BM25 index alongside
  your existing Pinecone data (existing Pinecone vectors are untouched;
  this just backfills the BM25 side).

- Rate limiter and semantic cache are in-memory only — reset on restart,
  not shared across multiple app instances. A real multi-instance
  deployment needs Redis for both.
- Auth is a single shared API key, not per-user accounts/JWT — right-sized
  for a personal project, not a multi-tenant system.
- SQLite, not Postgres — correct choice for a single-instance deployment;
  would need to migrate for concurrent multi-writer production use.
- Guardrails are pattern-based (regex), not ML-based — will miss cleverly
  worded injection attempts.
- `embed.py` wipes and rebuilds the Pinecone index on every run — no
  incremental updates yet.
