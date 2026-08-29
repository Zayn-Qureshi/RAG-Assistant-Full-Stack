"""
Per-user authentication: bcrypt password hashing + JWT sessions.

Replaces the earlier shared-API-key approach — that was flagged in
SECURITY.md as unsuitable for an organization (no per-user identity, no
audit trail, no way to revoke one person's access). This gives each user
a real account and a signed token proving who they are.

Why JWT: once issued, a token is verified by checking its cryptographic
signature — fast, in-memory, no database round-trip per request (this is
the "cache" the person asked about — JWT verification IS that cache by
design). The one thing JWTs can't do natively is instant revocation
before natural expiry, which is why there's a small revoked_tokens table
consulted only at verification time.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Header, HTTPException

from database import get_user_by_id, is_token_revoked

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

if not JWT_SECRET:
    raise RuntimeError(
        "JWT_SECRET is not set in .env. Generate one with: "
        "python -c \"import secrets; print(secrets.token_hex(32))\" "
        "and add it as JWT_SECRET=<value> in your .env file. "
        "Refusing to start with no secret — that would make all tokens forgeable."
    )


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: int, username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "jti": str(uuid.uuid4()),  # unique token ID, used for revocation lookups
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired, please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session token")

    if is_token_revoked(payload["jti"]):
        raise HTTPException(status_code=401, detail="Session has been logged out")

    return payload


async def get_current_user(authorization: str = Header(default="")):
    """
    FastAPI dependency — extracts and verifies the JWT from the
    Authorization header ("Bearer <token>"), returns the current user's
    info. Add to any endpoint that requires a logged-in user.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_token(token)

    user = get_user_by_id(int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")

    return {"id": user["id"], "username": user["username"], "jti": payload["jti"]}
