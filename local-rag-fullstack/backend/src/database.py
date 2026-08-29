"""
SQLite database layer — multi-tenant schema.

Tables:
- users: one row per account (username, hashed password)
- conversations: one row per chat thread (a user can have many, like
  ChatGPT's conversation list)
- messages: every user/assistant message, linked to a conversation
  (which is linked to a user) — this is how chat history stays isolated
  per person
- query_logs: structured record of every RAG query, now tagged with
  user_id for a real per-user audit trail
- revoked_tokens: JWT IDs that have been explicitly logged out before
  their natural expiry (JWTs are otherwise stateless/fast, this table
  is only consulted for the logout-revocation edge case)
"""

import sqlite3
import json
import os
from contextlib import contextmanager
from datetime import datetime

DB_PATH = "data/app.db"

# Ensure the parent directory exists — sqlite3.connect does NOT create
# missing directories, only the file itself.
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL DEFAULT 'New conversation',
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                sources TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS query_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                conversation_id TEXT,
                query TEXT NOT NULL,
                retrieved_sources TEXT,
                latency_seconds REAL,
                cache_hit INTEGER DEFAULT 0,
                blocked_by_guardrail INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS revoked_tokens (
                jti TEXT PRIMARY KEY,
                revoked_at TEXT NOT NULL
            )
        """)


# --- Users ---
def create_user(username: str, password_hash: str) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username, password_hash, datetime.now().isoformat()),
        )
        return cursor.lastrowid


def get_user_by_username(username: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


# --- Conversations ---
def create_conversation(conversation_id: str, user_id: int, title: str = "New conversation"):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO conversations (id, user_id, title, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, user_id, title, datetime.now().isoformat()),
        )


def get_conversations(user_id: int) -> list[dict]:
    """List all conversations for a user, most recent first."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM conversations WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_conversation(conversation_id: str, user_id: int) -> dict | None:
    """Fetch one conversation, scoped to the owning user (prevents
    one user from reading another user's conversation by guessing an ID)."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        ).fetchone()
        return dict(row) if row else None


def update_conversation_title(conversation_id: str, title: str):
    with get_connection() as conn:
        conn.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conversation_id))


def delete_conversation(conversation_id: str, user_id: int):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM messages WHERE conversation_id = ? AND conversation_id IN "
            "(SELECT id FROM conversations WHERE id = ? AND user_id = ?)",
            (conversation_id, conversation_id, user_id),
        )
        conn.execute(
            "DELETE FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        )


# --- Messages ---
def add_message(conversation_id: str, role: str, content: str, sources: list[str] | None = None):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content, sources, created_at) VALUES (?, ?, ?, ?, ?)",
            (conversation_id, role, content, json.dumps(sources or []), datetime.now().isoformat()),
        )


def get_messages(conversation_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT role, content, sources, created_at FROM messages "
            "WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        ).fetchall()
        return [
            {
                "role": r["role"],
                "content": r["content"],
                "sources": json.loads(r["sources"]) if r["sources"] else [],
                "created_at": r["created_at"],
            }
            for r in rows
        ]


# --- Query logs ---
def log_query(
    user_id: int | None,
    conversation_id: str | None,
    query: str,
    retrieved_sources: list[str],
    latency_seconds: float = 0,
    cache_hit: bool = False,
    blocked_by_guardrail: bool = False,
):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO query_logs
               (user_id, conversation_id, query, retrieved_sources,
                latency_seconds, cache_hit, blocked_by_guardrail, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id, conversation_id, query, json.dumps(retrieved_sources),
                latency_seconds, int(cache_hit), int(blocked_by_guardrail),
                datetime.now().isoformat(),
            ),
        )


# --- Token revocation (for logout) ---
def revoke_token(jti: str):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO revoked_tokens (jti, revoked_at) VALUES (?, ?)",
            (jti, datetime.now().isoformat()),
        )


def is_token_revoked(jti: str) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT 1 FROM revoked_tokens WHERE jti = ?", (jti,)).fetchone()
        return row is not None
