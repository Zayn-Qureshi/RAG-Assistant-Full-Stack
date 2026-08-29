"""
Step 3: Hybrid retrieval, scoped per user.

Vector search uses a Pinecone NAMESPACE per user — same index, but
Pinecone guarantees a query in one namespace never returns vectors from
another namespace. Combined with per-user BM25 (bm25_index.py), this
means User A's search can never surface User B's documents.
"""

from pinecone import Pinecone

from config import PINECONE_API_KEY, PINECONE_INDEX_NAME, TOP_K
from embed import get_embedding
from bm25_index import bm25_search
from reranker import rerank

pc = Pinecone(api_key=PINECONE_API_KEY)

CANDIDATE_POOL_SIZE = 10


def get_index():
    return pc.Index(PINECONE_INDEX_NAME)


def _vector_search(user_id: str, query: str, top_k: int) -> list[dict]:
    index = get_index()
    query_vector = get_embedding(query, task_type="retrieval_query")

    results = index.query(
        vector=query_vector,
        top_k=top_k,
        include_metadata=True,
        namespace=user_id,  # <-- the actual isolation mechanism
    )

    return [
        {
            "id": match["id"],
            "text": match["metadata"]["text"],
            "source": match["metadata"]["source"],
            "chunk_id": match["metadata"]["chunk_id"],
            "vector_score": match["score"],
        }
        for match in results["matches"]
    ]


def retrieve(user_id: str, query: str, top_k: int = TOP_K, use_hybrid: bool = True) -> list[dict]:
    vector_results = _vector_search(user_id, query, top_k=CANDIDATE_POOL_SIZE)

    if not use_hybrid:
        return [
            {**r, "distance": round(1 - r["vector_score"], 4)}
            for r in vector_results[:top_k]
        ]

    bm25_results = bm25_search(user_id, query, top_k=CANDIDATE_POOL_SIZE)

    merged = {}
    for r in vector_results:
        key = (r["source"], r["chunk_id"])
        merged[key] = {"text": r["text"], "source": r["source"], "chunk_id": r["chunk_id"]}
    for r in bm25_results:
        key = (r["source"], r["chunk_id"])
        merged.setdefault(key, {"text": r["text"], "source": r["source"], "chunk_id": r["chunk_id"]})

    candidates = list(merged.values())
    reranked = rerank(query, candidates, top_k=top_k)

    return [
        {**r, "distance": round(-r["rerank_score"], 4)}
        for r in reranked
    ]
