"""
Simple caching layer to avoid paying API cost/latency for repeated questions.

Two-tier approach:
1. Exact-match cache (instant, free) — catches literal repeats.
2. Semantic cache (embedding similarity) — catches paraphrased repeats,
   e.g. "what is zain's email" vs "zain email address" should hit the
   same cached answer.

In-memory only (resets when the app restarts). For a real production
system you'd back this with Redis so it persists across restarts and
is shared across multiple app instances — noted in README as a
known next step, not implemented here to keep this dependency-light.
"""

import time
import numpy as np

from embed import get_embedding

SIMILARITY_THRESHOLD = 0.95  # cosine similarity above this = "same question"
CACHE_TTL_SECONDS = 3600      # cached answers expire after 1 hour


class SemanticCache:
    def __init__(self):
        self._exact_cache = {}   # {query_lower: (answer_dict, timestamp)}
        self._semantic_cache = []  # list of (embedding, query, answer_dict, timestamp)

    def _is_expired(self, timestamp: float) -> bool:
        return (time.time() - timestamp) > CACHE_TTL_SECONDS

    def get(self, user_id: str, query: str):
        """Returns cached answer dict if found (exact or semantic match, scoped to this user), else None."""
        key = f"{user_id}:{query.strip().lower()}"

        # 1. Exact match
        if key in self._exact_cache:
            answer, timestamp = self._exact_cache[key]
            if not self._is_expired(timestamp):
                return answer
            del self._exact_cache[key]  # expired, evict

        # 2. Semantic match — only compare against this same user's entries
        user_entries = [e for e in self._semantic_cache if e[4] == user_id]
        if user_entries:
            query_embedding = np.array(get_embedding(query, task_type="retrieval_query"))
            best_score = -1
            best_match = None

            for cached_embedding, cached_query, cached_answer, timestamp, _ in user_entries:
                if self._is_expired(timestamp):
                    continue
                score = self._cosine_similarity(query_embedding, np.array(cached_embedding))
                if score > best_score:
                    best_score = score
                    best_match = cached_answer

            if best_score >= SIMILARITY_THRESHOLD:
                return best_match

        return None

    def set(self, user_id: str, query: str, answer: dict):
        """Store a query/answer pair, scoped to this user."""
        key = f"{user_id}:{query.strip().lower()}"
        timestamp = time.time()

        self._exact_cache[key] = (answer, timestamp)

        query_embedding = get_embedding(query, task_type="retrieval_query")
        self._semantic_cache.append((query_embedding, query, answer, timestamp, user_id))

        # keep semantic cache from growing unbounded in a long session
        if len(self._semantic_cache) > 500:
            self._semantic_cache = self._semantic_cache[-500:]

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


# module-level singleton so the whole app shares one cache instance
cache = SemanticCache()
