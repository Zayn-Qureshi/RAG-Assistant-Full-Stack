"""
Step 4: Build a grounded prompt from retrieved chunks and call Gemini
to generate an answer — scoped per user throughout (retrieval, cache).
"""

import google.generativeai as genai

from config import GEMINI_API_KEY, GEMINI_LLM_MODEL
from retrieve import retrieve
from cache import cache
from guardrails import filter_query, filter_retrieved_chunks
from cost_tracker import log_usage
from utils import logger, retry_with_backoff

genai.configure(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """You are a helpful assistant answering questions using ONLY the context provided below.

Rules:
- If the answer is not contained in the context, say "I don't have enough information in the provided documents to answer that."
- Do not use outside knowledge, even if you know the answer.
- Cite which source each part of your answer comes from when possible.
- Be concise and direct."""


def build_prompt(query: str, retrieved_chunks: list[dict]) -> str:
    context_blocks = []
    for chunk in retrieved_chunks:
        context_blocks.append(f"[Source: {chunk['source']}]\n{chunk['text']}")
    context = "\n\n---\n\n".join(context_blocks)

    return f"""{SYSTEM_PROMPT}

Context:
{context}

Question: {query}

Answer:"""


@retry_with_backoff(max_retries=3, base_delay=1.0)
def _call_gemini(prompt: str):
    model = genai.GenerativeModel(GEMINI_LLM_MODEL)
    return model.generate_content(prompt)


def generate_answer(user_id: str, query: str, top_k: int = 3) -> dict:
    """
    Full RAG call, scoped to one user's documents and cache.
    """
    logger.info(f"[user={user_id}] Query received: {query}")

    is_safe, message = filter_query(query)
    if not is_safe:
        logger.warning(f"[user={user_id}] Query blocked by guardrail: {message}")
        return {"answer": message, "sources": [], "retrieved_chunks": []}

    cached = cache.get(user_id, query)
    if cached:
        logger.info(f"[user={user_id}] Cache hit — skipping API call")
        return cached

    retrieved_chunks = retrieve(user_id, query, top_k=top_k)
    retrieved_chunks = filter_retrieved_chunks(retrieved_chunks)

    if not retrieved_chunks:
        return {
            "answer": "No relevant documents found. Have you uploaded any documents yet?",
            "sources": [],
            "retrieved_chunks": [],
        }

    prompt = build_prompt(query, retrieved_chunks)
    response = _call_gemini(prompt)
    answer = response.text

    usage = response.usage_metadata
    log_usage(query, usage.prompt_token_count, usage.candidates_token_count)
    logger.info(
        f"[user={user_id}] Answered — input_tokens={usage.prompt_token_count} "
        f"output_tokens={usage.candidates_token_count}"
    )

    sources = sorted(set(c["source"] for c in retrieved_chunks))
    result = {"answer": answer.strip(), "sources": sources, "retrieved_chunks": retrieved_chunks}

    cache.set(user_id, query, result)

    return result


def generate_answer_stream(user_id: str, query: str, top_k: int = 3):
    """Streaming version, scoped to one user's documents and cache."""
    logger.info(f"[user={user_id}] Query received (stream): {query}")

    is_safe, message = filter_query(query)
    if not is_safe:
        logger.warning(f"[user={user_id}] Query blocked by guardrail: {message}")
        yield {"type": "token", "text": message}
        yield {"type": "done", "sources": [], "retrieved_chunks": []}
        return

    cached = cache.get(user_id, query)
    if cached:
        logger.info(f"[user={user_id}] Cache hit — skipping API call")
        yield {"type": "token", "text": cached["answer"]}
        yield {"type": "done", "sources": cached["sources"], "retrieved_chunks": cached["retrieved_chunks"]}
        return

    retrieved_chunks = retrieve(user_id, query, top_k=top_k)
    retrieved_chunks = filter_retrieved_chunks(retrieved_chunks)

    if not retrieved_chunks:
        yield {"type": "token", "text": "No relevant documents found. Have you uploaded any documents yet?"}
        yield {"type": "done", "sources": [], "retrieved_chunks": []}
        return

    prompt = build_prompt(query, retrieved_chunks)
    sources = sorted(set(c["source"] for c in retrieved_chunks))

    model = genai.GenerativeModel(GEMINI_LLM_MODEL)
    response_stream = model.generate_content(prompt, stream=True)

    full_answer = ""
    for chunk in response_stream:
        if chunk.text:
            full_answer += chunk.text
            yield {"type": "token", "text": chunk.text}

    result = {"answer": full_answer.strip(), "sources": sources, "retrieved_chunks": retrieved_chunks}
    cache.set(user_id, query, result)
    logger.info(f"[user={user_id}] Answered (stream) — {len(full_answer)} chars")

    yield {"type": "done", "sources": sources, "retrieved_chunks": retrieved_chunks}
