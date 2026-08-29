"""
Central config. Change model names / settings here — nowhere else.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Gemini ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_LLM_MODEL = "gemini-3.6-flash"
GEMINI_EMBED_MODEL = "models/gemini-embedding-001"

# --- Pinecone ---
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = "local-rag-index"
PINECONE_EMBED_DIMENSION = 3072  # gemini-embedding-001 output size

# --- Paths ---
RAW_DATA_DIR = "data/raw"

# --- Chunking ---
CHUNK_SIZE = 500       # tokens (approx, we use characters * 4 as rough proxy)
CHUNK_OVERLAP = 75     # ~15% overlap

# --- Retrieval ---
TOP_K = 3
