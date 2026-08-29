# Local RAG Frontend (React + Vite)

Chat UI that talks to the FastAPI backend (`local-rag-cloud/api.py`) over REST.

## Prerequisites

- Node.js installed (v18+ recommended) — check with `node --version`
- The FastAPI backend running (`uvicorn api:app --reload --port 8000` from
  the `local-rag-cloud` project)

## Setup

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Configure environment:**
   Copy `.env.example` to `.env` and set:
   ```
   VITE_API_BASE_URL=http://localhost:8000
   VITE_API_KEY=same_key_as_APP_API_KEY_in_the_backend
   ```
   The API key here must match `APP_API_KEY` in the backend's `.env` —
   if the backend has no `APP_API_KEY` set, auth is open and this can
   be left blank.

3. **Run the dev server:**
   ```bash
   npm run dev
   ```
   Opens at `http://localhost:5173`

## How it works

- `src/api.js` — all backend communication (fetch wrapper with API key header)
- `src/App.jsx` — chat UI, message state, session ID (persisted in
  localStorage so refreshing the page keeps your history — the backend's
  SQLite database remembers the conversation server-side)
- `src/App.css` — plain CSS, no framework

## Notes

- This is a REST-based UI, not streaming — each query waits for the full
  answer before displaying it (backend's `/query` endpoint isn't a
  streaming endpoint). Streamlit's version streams token-by-token; this
  doesn't yet. Worth adding later via Server-Sent Events if you want
  feature parity.
- CORS must be enabled on the backend for this to work cross-origin —
  already configured in `api.py`.
