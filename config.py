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
LLM_MODEL    = os.getenv("LLM_MODEL",  "qwen2.5:14b")

# mxbai-embed-large requires this prefix for query (not document) embeddings.
# If switching EMBED_MODEL to a model that doesn't use instructional prefixes,
# set QUERY_PREFIX="" via env var to avoid degraded retrieval quality.
QUERY_PREFIX = os.getenv("QUERY_PREFIX", "Represent this sentence for searching relevant passages: ")

# --- Ingestion tuning ---
CHUNK_SIZE    = int(os.getenv("CHUNK_SIZE",    "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
BATCH_LIMIT   = int(os.getenv("BATCH_LIMIT",   "20"))

# --- RAG retrieval ---
DEFAULT_N = int(os.getenv("DEFAULT_N", "20"))

# --- Ollama inference ---
NUM_CTX = int(os.getenv("NUM_CTX", "32768"))

# --- RAG quality ---
# Maximum L2 distance for ChromaDB results; chunks above this threshold are
# excluded from LLM context. Raise or set to inf to disable filtering.
MAX_DISTANCE = float(os.getenv("MAX_DISTANCE", "1.0"))

# --- Live alerts ---
MAX_ALERTS       = int(os.getenv("MAX_ALERTS",       "10"))   # max alerts to fetch and display
ALERT_CACHE_TTL  = int(os.getenv("ALERT_CACHE_TTL",  "120"))  # seconds to cache alert results

# Keywords that route a chat prompt to the RAG (documentation) path instead of
# Aria Ops. Add or remove words here to tune routing without touching the UI code.
UI_DOC_KEYWORDS: frozenset[str] = frozenset({
    "vcf", "nsx", "vsan", "vsphere", "esxi", "vcenter", "vcentre",
    "configure", "install", "deploy", "setup", "architecture",
    "storage", "network", "cluster", "sddc", "documentation", "manual",
})

# Severity → emoji icon mapping for alert display.
UI_SEVERITY_ICON: dict[str, str] = {
    "CRITICAL":    "🔴",
    "IMMEDIATE":   "🟠",
    "WARNING":     "🟡",
    "INFORMATION": "🟢",
}

# Answer-style presets shown in the sidebar temperature selector.
UI_TEMP_OPTIONS: dict[str, float] = {
    "Precise":      0.1,
    "Balanced":     0.4,
    "Creative":     0.7,
    "Experimental": 1.0,
}
