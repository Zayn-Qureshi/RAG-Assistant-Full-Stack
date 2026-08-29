"""
Re-ranking: takes the combined candidate set from vector search + BM25,
and re-scores each one with a cross-encoder model for more accurate
final ordering before the top-k get sent to the LLM.

Why this matters: vector search and BM25 each score a query against a
chunk independently and fairly cheaply. A cross-encoder looks at the
query and chunk TOGETHER (more expensive, but much more accurate) —
it's the standard second-stage refinement in real retrieval systems.

Uses a small local cross-encoder (via sentence-transformers) rather than
an API, so re-ranking doesn't add extra API cost or another network
round-trip on top of Gemini/Pinecone.
"""

from sentence_transformers import CrossEncoder

_model = None  # lazy-loaded on first use, since loading takes a moment


def _get_model():
    global _model
    if _model is None:
        # small, fast, well-regarded cross-encoder for this exact task
        _model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _model


def rerank(query: str, candidates: list[dict], top_k: int = 3) -> list[dict]:
    """
    candidates: list of dicts with at least a "text" key (from vector
    search and/or BM25, already deduplicated by caller).
    Returns the top_k candidates, re-sorted by cross-encoder relevance,
    with a "rerank_score" added to each.
    """
    if not candidates:
        return []

    model = _get_model()
    pairs = [(query, c["text"]) for c in candidates]
    scores = model.predict(pairs)

    for candidate, score in zip(candidates, scores):
        candidate["rerank_score"] = float(score)

    ranked = sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)
    return ranked[:top_k]
