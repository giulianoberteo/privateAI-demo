"""
Centralised configuration for privateAI-demo.

Every tuneable constant lives here so that changing the embedding model,
LLM, or Ollama endpoint in one place propagates to all scripts.
Override any value with the matching environment variable.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# --- Vector Store ---
DB_PATH = BASE_DIR / "rag" / "chroma_db"

# Version registry: maps semantic version → ChromaDB collection name.
# Add a new entry here whenever a new VCF version is ingested.
VERSION_MAP: dict[str, str] = {
    "9.0": "docs_vcf90",
    "9.1": "docs_vcf91",
}
DEFAULT_VERSION = os.getenv("DEFAULT_VERSION", "9.1")

# --- Ollama endpoints ---
OLLAMA_URL   = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL  = os.getenv("EMBED_MODEL", "mxbai-embed-large")
LLM_MODEL    = os.getenv("LLM_MODEL",  "qwen3.5:35b-a3b")

# Mxbai-embed-large requires this prefix for query (not document) embeddings.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

# --- Ingestion tuning ---
CHUNK_SIZE    = int(os.getenv("CHUNK_SIZE",    "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
BATCH_LIMIT   = int(os.getenv("BATCH_LIMIT",   "20"))

# --- RAG retrieval ---
DEFAULT_N = int(os.getenv("DEFAULT_N", "20"))

# --- Ollama inference ---
NUM_CTX = int(os.getenv("NUM_CTX", "32768"))
