"""
Two production-standard concerns that don't fit neatly elsewhere:

1. Retry with exponential backoff — external APIs (Gemini, Pinecone) can
   fail transiently (network blip, rate limit, momentary server issue).
   Without retry logic, one bad moment crashes the whole request instead
   of quietly recovering.

2. Structured logging — right now, if something fails, there's no record
   of what query caused it or why. This is the minimum viable observability
   every production system needs before reaching for a bigger tool
   (Langfuse, Datadog, etc).
"""

import logging
import time
import functools

# --- Structured logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/app.log", encoding="utf-8"),
        logging.StreamHandler(),  # also print to console
    ],
)

logger = logging.getLogger("rag_app")


# --- Retry with exponential backoff ---
def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """
    Decorator: retries a function on exception, waiting base_delay * 2^attempt
    seconds between tries (1s, 2s, 4s, ...). Logs each failed attempt.

    Usage:
        @retry_with_backoff(max_retries=3)
        def call_api(...):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    wait_time = base_delay * (2 ** attempt)
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    if attempt < max_retries - 1:
                        time.sleep(wait_time)
            logger.error(f"{func.__name__} failed after {max_retries} attempts: {last_exception}")
            raise last_exception
        return wrapper
    return decorator
