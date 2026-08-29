"""
FastAPI backend — multi-tenant version.

Endpoints:
- POST /auth/signup          — create an account
- POST /auth/login           — get a JWT session token
- POST /auth/logout          — revoke the current token
- GET  /conversations         — list this user's conversations
- POST /conversations         — start a new conversation
- GET  /conversations/{id}    — get one conversation's messages
- DELETE /conversations/{id}  — delete a conversation
- POST /query                 — ask a question (scoped to this user's documents)
- POST /ingest                — upload a document (scoped to this user)
- GET  /documents             — list this user's uploaded documents
- DELETE /documents/{filename} — remove one of this user's documents
- GET  /usage                 — token/cost usage summary
- GET  /health                — liveness check

Run with: uvicorn api:app --reload --port 8000
Docs at: http://localhost:8000/docs
"""

import time
import uuid
import sys
import os
import asyncio

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from fastapi import FastAPI, Depends, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from generate import generate_answer
from database import (
    init_db, create_user, get_user_by_username,
    create_conversation, get_conversations, get_conversation,
    delete_conversation, update_conversation_title,
    add_message, get_messages, log_query, revoke_token,
)
from auth import hash_password, verify_password, create_access_token, get_current_user
from cost_tracker import get_usage_summary
from rate_limiter import rate_limit
from utils import logger
from ingest import ingest_single_file, delete_document, list_user_documents, user_raw_dir

app = FastAPI(title="Local RAG API", version="2.0")

_allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.on_event("startup")
def startup():
    init_db()
    logger.info("API started, database initialized")


# --- Request/response models ---
class SignupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=200)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    username: str


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: str


class NewConversationRequest(BaseModel):
    title: str = Field(default="New conversation", max_length=100)


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str
    top_k: int = Field(default=3, ge=1, le=10)


class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    latency_seconds: float


class HistoryMessage(BaseModel):
    role: str
    content: str
    sources: list[str]
    created_at: str


class IngestResponse(BaseModel):
    filename: str
    chunks_added: int
    message: str


# --- Auth endpoints ---
@app.post("/auth/signup", response_model=TokenResponse)
async def signup(req: SignupRequest):
    if get_user_by_username(req.username):
        raise HTTPException(status_code=400, detail="Username already taken")

    password_hash = hash_password(req.password)
    user_id = create_user(req.username, password_hash)
    token = create_access_token(user_id, req.username)

    logger.info(f"New user signed up: {req.username}")
    return TokenResponse(access_token=token, username=req.username)


@app.post("/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    user = get_user_by_username(req.username)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token(user["id"], user["username"])
    logger.info(f"User logged in: {req.username}")
    return TokenResponse(access_token=token, username=user["username"])


@app.post("/auth/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    revoke_token(current_user["jti"])
    logger.info(f"User logged out: {current_user['username']}")
    return {"message": "Logged out"}


# --- Conversation endpoints ---
@app.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(current_user: dict = Depends(get_current_user)):
    return get_conversations(current_user["id"])


@app.post("/conversations", response_model=ConversationSummary)
async def new_conversation(req: NewConversationRequest, current_user: dict = Depends(get_current_user)):
    conversation_id = str(uuid.uuid4())
    create_conversation(conversation_id, current_user["id"], req.title)
    return ConversationSummary(id=conversation_id, title=req.title, created_at="")


@app.get("/conversations/{conversation_id}", response_model=list[HistoryMessage])
async def conversation_messages(conversation_id: str, current_user: dict = Depends(get_current_user)):
    convo = get_conversation(conversation_id, current_user["id"])
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return get_messages(conversation_id)


@app.delete("/conversations/{conversation_id}")
async def remove_conversation(conversation_id: str, current_user: dict = Depends(get_current_user)):
    convo = get_conversation(conversation_id, current_user["id"])
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    delete_conversation(conversation_id, current_user["id"])
    return {"message": "Conversation deleted"}


# --- Query endpoint ---
@app.post("/query", response_model=QueryResponse, dependencies=[Depends(rate_limit)])
async def query(req: QueryRequest, current_user: dict = Depends(get_current_user)):
    convo = get_conversation(req.conversation_id, current_user["id"])
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    start = time.time()
    result = await asyncio.to_thread(generate_answer, str(current_user["id"]), req.query, req.top_k)
    latency = time.time() - start

    add_message(req.conversation_id, "user", req.query)
    add_message(req.conversation_id, "assistant", result["answer"], result["sources"])

    # auto-title a fresh conversation from its first message
    if convo["title"] == "New conversation":
        update_conversation_title(req.conversation_id, req.query[:60])

    log_query(
        user_id=current_user["id"],
        conversation_id=req.conversation_id,
        query=req.query,
        retrieved_sources=result["sources"],
        latency_seconds=round(latency, 2),
    )

    return QueryResponse(answer=result["answer"], sources=result["sources"], latency_seconds=round(latency, 2))


# --- Document endpoints ---
@app.get("/documents")
async def documents(current_user: dict = Depends(get_current_user)):
    return {"documents": list_user_documents(current_user["id"])}


@app.post("/ingest", response_model=IngestResponse, dependencies=[Depends(rate_limit)])
async def ingest(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    allowed_extensions = (".pdf", ".txt", ".md")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(allowed_extensions)}")

    contents = await file.read()
    max_size_bytes = 20 * 1024 * 1024
    if len(contents) > max_size_bytes:
        raise HTTPException(status_code=400, detail="File too large (max 20MB)")

    if ext == ".pdf" and not contents.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="File does not appear to be a valid PDF")

    safe_filename = os.path.basename(file.filename).replace("\\", "").replace("/", "")
    if not safe_filename or safe_filename in (".", ".."):
        raise HTTPException(status_code=400, detail="Invalid filename")

    user_dir = user_raw_dir(current_user["id"])
    save_path = os.path.join(user_dir, safe_filename)
    if not os.path.abspath(save_path).startswith(os.path.abspath(user_dir)):
        raise HTTPException(status_code=400, detail="Invalid file path")

    with open(save_path, "wb") as f:
        f.write(contents)

    logger.info(f"[user={current_user['id']}] File uploaded: {safe_filename} ({len(contents)} bytes)")

    try:
        result = await asyncio.to_thread(ingest_single_file, str(current_user["id"]), save_path)
    except Exception as e:
        logger.error(f"[user={current_user['id']}] Ingestion failed for {safe_filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

    return IngestResponse(
        filename=result["filename"],
        chunks_added=result["chunks_added"],
        message=f"Successfully indexed {result['chunks_added']} chunks from {result['filename']}",
    )


@app.delete("/documents/{filename}")
async def remove_document(filename: str, current_user: dict = Depends(get_current_user)):
    try:
        await asyncio.to_thread(delete_document, str(current_user["id"]), filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")
    return {"message": f"Deleted {filename}"}


# --- Misc ---
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/usage")
async def usage(current_user: dict = Depends(get_current_user)):
    return get_usage_summary()
