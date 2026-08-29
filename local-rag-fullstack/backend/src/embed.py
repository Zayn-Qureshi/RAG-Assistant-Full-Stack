"""
Step 2: Embed chunks using Gemini's embedding model, store in Pinecone.

Run this once (or whenever your documents change) to build/update the index.
"""

import time
import google.generativeai as genai
from pinecone import Pinecone, ServerlessSpec

from config import (
    GEMINI_API_KEY,
    GEMINI_EMBED_MODEL,
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    PINECONE_EMBED_DIMENSION,
)
from loader import load_and_chunk_all
from bm25_index import build_bm25_index

genai.configure(api_key=GEMINI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)


def get_embedding(text: str, task_type: str = "retrieval_document") -> list[float]:
    """
    Call Gemini's embedding endpoint.
    task_type: "retrieval_document" for chunks being indexed,
               "retrieval_query" for the user's question at search time.
    """
    result = genai.embed_content(
        model=GEMINI_EMBED_MODEL,
        content=text,
        task_type=task_type,
    )
    return result["embedding"]


def get_or_create_index():
    existing_indexes = [idx["name"] for idx in pc.list_indexes()]
    if PINECONE_INDEX_NAME not in existing_indexes:
        print(f"Creating Pinecone index '{PINECONE_INDEX_NAME}'...")
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=PINECONE_EMBED_DIMENSION,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        while not pc.describe_index(PINECONE_INDEX_NAME).status["ready"]:
            time.sleep(1)
    return pc.Index(PINECONE_INDEX_NAME)


def build_index(chunks: list[dict]):
    """
    Embed every chunk and upsert into Pinecone.
    Wipes existing vectors first so re-runs don't duplicate data.
    """
    index = get_or_create_index()

    try:
        index.delete(delete_all=True)
    except Exception:
        pass  # index might already be empty

    vectors = []
    for i, chunk in enumerate(chunks):
        print(f"Embedding chunk {i + 1}/{len(chunks)} ({chunk['source']})...")
        vector = get_embedding(chunk["text"], task_type="retrieval_document")

        vectors.append({
            "id": f"{chunk['source']}_{chunk['chunk_id']}",
            "values": vector,
            "metadata": {
                "source": chunk["source"],
                "chunk_id": chunk["chunk_id"],
                "text": chunk["text"],  # stored in metadata so retrieve.py can pull it back
            },
        })

    batch_size = 100
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i + batch_size]
        index.upsert(vectors=batch)

    print(f"\n✅ Indexed {len(chunks)} chunks into Pinecone index '{PINECONE_INDEX_NAME}'")

    build_bm25_index(chunks)
    print(f"✅ Built BM25 keyword index alongside it")

    return index


if __name__ == "__main__":
    # NOTE: this batch-build path is now a legacy/admin tool. In the
    # multi-tenant version, users upload documents through the app
    # (POST /ingest), which scopes everything to their own Pinecone
    # namespace and BM25 store automatically. This script has no
    # concept of "which user" and would need a --user-id argument to
    # be useful again — left here only as a reference for the original
    # single-tenant batch flow.
    print("This script is for the old single-tenant setup. Use the app's")
    print("upload feature instead — it handles per-user isolation correctly.")
