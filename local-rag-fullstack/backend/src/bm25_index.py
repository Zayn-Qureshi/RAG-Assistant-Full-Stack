"""
BM25 keyword index — the "keyword" half of hybrid search.

Now scoped PER USER: each user has their own store file and in-memory
index, so User A's keyword search never returns User B's document
chunks. This mirrors the Pinecone namespace isolation on the vector
search side.
"""

import json
import os
from rank_bm25 import BM25Okapi

BM25_STORE_DIR = "data/bm25_stores"

# In-memory indexes, keyed by user_id — avoids rebuilding from disk on
# every single search call within the same process.
_bm25_indexes: dict[str, BM25Okapi] = {}
_bm25_entries: dict[str, list[dict]] = {}


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


def _store_path(user_id: str) -> str:
    return os.path.join(BM25_STORE_DIR, f"{user_id}.json")


def _load_store(user_id: str) -> list[dict]:
    path = _store_path(user_id)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_store(user_id: str, entries: list[dict]):
    os.makedirs(BM25_STORE_DIR, exist_ok=True)
    with open(_store_path(user_id), "w", encoding="utf-8") as f:
        json.dump(entries, f)


def _rebuild_index(user_id: str):
    entries = _load_store(user_id)
    _bm25_entries[user_id] = entries
    if entries:
        tokenized = [_tokenize(e["text"]) for e in entries]
        _bm25_indexes[user_id] = BM25Okapi(tokenized)
    else:
        _bm25_indexes[user_id] = None


def build_bm25_index(user_id: str, chunks: list[dict]):
    """Full rebuild for one user — used during that user's batch ingestion."""
    entries = [
        {"id": f"{c['source']}_{c['chunk_id']}", "source": c["source"], "chunk_id": c["chunk_id"], "text": c["text"]}
        for c in chunks
    ]
    _save_store(user_id, entries)
    _rebuild_index(user_id)


def add_to_bm25_index(user_id: str, new_entries: list[dict]):
    """Incremental add for one user — used when they upload a single new document."""
    existing = _load_store(user_id)
    existing.extend(new_entries)
    _save_store(user_id, existing)
    _rebuild_index(user_id)


def remove_from_bm25_index(user_id: str, source: str):
    """Remove all chunks belonging to one document (used when a user deletes a document)."""
    existing = _load_store(user_id)
    filtered = [e for e in existing if e["source"] != source]
    _save_store(user_id, filtered)
    _rebuild_index(user_id)


def bm25_search(user_id: str, query: str, top_k: int = 5) -> list[dict]:
    """Returns top-k chunks by BM25 score, scoped to this user's documents only."""
    if user_id not in _bm25_indexes:
        _rebuild_index(user_id)

    index = _bm25_indexes.get(user_id)
    entries = _bm25_entries.get(user_id, [])
    if index is None or not entries:
        return []

    tokenized_query = _tokenize(query)
    scores = index.get_scores(tokenized_query)

    ranked = sorted(zip(entries, scores), key=lambda x: x[1], reverse=True)[:top_k]

    return [
        {"text": entry["text"], "source": entry["source"], "chunk_id": entry["chunk_id"], "bm25_score": float(score)}
        for entry, score in ranked
        if score > 0
    ]


def list_documents(user_id: str) -> list[str]:
    """Returns the distinct source filenames this user has indexed."""
    entries = _load_store(user_id)
    return sorted(set(e["source"] for e in entries))
