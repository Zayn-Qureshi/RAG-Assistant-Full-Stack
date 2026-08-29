"""
Per-user incremental document management: ingest a new file, or remove
an existing one — both scoped to one user's Pinecone namespace and BM25
store, never touching other users' data.
"""

import os
import shutil

from loader import load_pdf, load_text_file, chunk_text
from embed import get_embedding, get_or_create_index
from bm25_index import add_to_bm25_index, remove_from_bm25_index, list_documents

RAW_DATA_ROOT = "data/raw"


def user_raw_dir(user_id: str) -> str:
    """Each user's uploaded files live in their own subfolder."""
    path = os.path.join(RAW_DATA_ROOT, str(user_id))
    os.makedirs(path, exist_ok=True)
    return path


def ingest_single_file(user_id: str, filepath: str) -> dict:
    """
    Chunk, embed, and upsert ONE document into this user's Pinecone
    namespace + BM25 store, without touching any other user's data or
    this user's other existing documents.
    """
    filename = os.path.basename(filepath)
    ext = os.path.splitext(filename)[1].lower()

    if ext == ".pdf":
        text = load_pdf(filepath)
    elif ext in (".txt", ".md"):
        text = load_text_file(filepath)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    if not text.strip():
        raise ValueError(f"No extractable text found in {filename}")

    chunks = chunk_text(text)
    index = get_or_create_index()

    vectors = []
    bm25_entries = []

    for i, chunk_content in enumerate(chunks):
        vector = get_embedding(chunk_content, task_type="retrieval_document")
        chunk_id = f"{filename}_{i}"

        vectors.append({
            "id": chunk_id,
            "values": vector,
            "metadata": {"source": filename, "chunk_id": i, "text": chunk_content},
        })
        bm25_entries.append({"id": chunk_id, "source": filename, "chunk_id": i, "text": chunk_content})

    batch_size = 100
    for i in range(0, len(vectors), batch_size):
        index.upsert(vectors=vectors[i:i + batch_size], namespace=str(user_id))

    add_to_bm25_index(str(user_id), bm25_entries)

    return {"filename": filename, "chunks_added": len(chunks)}


def delete_document(user_id: str, filename: str):
    """
    Remove one document from a user's index entirely: Pinecone vectors,
    BM25 entries, and the raw uploaded file.
    """
    index = get_or_create_index()

    # Pinecone: delete by metadata filter (all chunks with this source),
    # scoped to this user's namespace so it can't affect anyone else's data
    index.delete(filter={"source": filename}, namespace=str(user_id))

    remove_from_bm25_index(str(user_id), filename)

    raw_path = os.path.join(user_raw_dir(user_id), filename)
    if os.path.exists(raw_path):
        os.remove(raw_path)


def list_user_documents(user_id: str) -> list[str]:
    return list_documents(str(user_id))


def delete_all_user_data(user_id: str):
    """Used if a user account is ever deleted entirely — removes everything."""
    index = get_or_create_index()
    try:
        index.delete(delete_all=True, namespace=str(user_id))
    except Exception:
        pass  # namespace might not exist / already empty

    for filename in list_documents(str(user_id)):
        remove_from_bm25_index(str(user_id), filename)

    user_dir = user_raw_dir(user_id)
    if os.path.exists(user_dir):
        shutil.rmtree(user_dir)
