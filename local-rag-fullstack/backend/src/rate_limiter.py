"""
Simple in-memory sliding-window rate limiter, keyed by client IP.

In-memory only — resets on restart, and doesn't share state across multiple
app instances. That's fine for a single-instance personal project; a real
multi-instance deployment would back this with Redis, same caveat as the
semantic cache. Documented in README, not hidden.
"""

import time
from collections import defaultdict, deque
from fastapi import Request, HTTPException

MAX_REQUESTS = 20        # per window
WINDOW_SECONDS = 60      # 20 requests per 60 seconds per client

_request_log: dict[str, deque] = defaultdict(deque)


async def rate_limit(request: Request):
    """FastAPI dependency — add to any endpoint that should be rate-limited."""
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()

    log = _request_log[client_ip]

    # drop timestamps outside the window
    while log and log[0] < now - WINDOW_SECONDS:
        log.popleft()

    if len(log) >= MAX_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: max {MAX_REQUESTS} requests per {WINDOW_SECONDS}s",
        )

    log.append(now)
