# Local RAG Assistant — Full Stack

A production-oriented RAG system: FastAPI + Gemini + Pinecone backend,
React frontend. Everything in one folder, but backend and frontend are
still two separate running processes (this is normal — a "monorepo"
holds multiple related projects together without merging their runtimes).

```
local-rag-fullstack/
├── backend/          FastAPI API + RAG pipeline (Gemini, Pinecone, SQLite)
├── frontend/          React chat UI (Vite)
└── README.md          (this file)
```

## Quick start

You need **two terminals running at the same time** — the backend serves
the API, the frontend is a separate web app that calls it over HTTP.

### Terminal 1 — Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows
# source .venv/bin/activate       # Mac/Linux

pip install -r requirements.txt

# Copy .env.example to .env and fill in your real keys:
#   GEMINI_API_KEY, PINECONE_API_KEY, APP_API_KEY

# Add your PDFs to backend/data/raw/, then build the index:
python src\embed.py

# Start the API:
uvicorn api:app --reload --port 8000
```
Backend runs at `http://localhost:8000` — interactive docs at `/docs`.

### Terminal 2 — Frontend

```bash
cd frontend
npm install

# Copy .env.example to .env — VITE_API_KEY must match backend's APP_API_KEY

npm run dev
```
Frontend runs at `http://localhost:5173` — open this in your browser.

## What's in each folder

See `backend/README.md` and `frontend/README.md` for full details on
each part — architecture, all implemented concepts (caching, guardrails,
auth, rate limiting, SQLite, Docker, etc.), and known limitations.

## Also included: Streamlit UI

`backend/app.py` is a second, simpler UI (Streamlit) that talks directly
to the pipeline without going through the FastAPI layer — useful as a
quick debug view alongside the React frontend. Run with:
```bash
cd backend
streamlit run app.py
```
