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

# Words that signal the user is asking about VCF *documentation* (architecture,
# installation, configuration) rather than live operational data.
# Deliberately excludes product/component names (sddc, nsx, vsan, cluster…)
# because those appear equally in operational questions like "any nsx alerts?".
UI_DOC_KEYWORDS: frozenset[str] = frozenset({
    "configure", "install", "deploy", "setup",
    "architecture", "documentation", "manual", "blueprint", "design",
})

# Words that signal an *operational/alert* intent. When any of these appear,
# the alert path is taken even if doc keywords are also present — e.g.
# "Do I have any alerts in my SDDC?" contains "sddc" (now NOT a doc keyword)
# but "alerts" wins and routes to Aria Ops.
UI_ALERT_KEYWORDS: frozenset[str] = frozenset({
    "alert", "alerts", "alarm", "alarms",
    "health", "issue", "issues", "problem", "problems",
    "critical", "warning", "warnings", "degraded", "down",
    "fault", "faults", "monitoring", "ops", "operations",
})

# Severity → emoji icon mapping for alert display.
UI_SEVERITY_ICON: dict[str, str] = {
    "CRITICAL":    "🔴",
    "IMMEDIATE":   "🟠",
    "WARNING":     "🟡",
    "INFORMATION": "🟢",
}

# --- UI presentation ---
UI_PAGE_TITLE = os.getenv("UI_PAGE_TITLE", "🦅 VCF vArchitect Agent")
UI_PAGE_ICON  = os.getenv("UI_PAGE_ICON",  "🦅")

# Shadow cost rates (USD per 1 million tokens) used to estimate what the same
# conversation would cost on a cloud API. These are not real charges — Ollama
# runs locally for free. Defaults approximate GPT-4o mini pricing (a fair
# comparison for a 14B-class model).
#   Input  ~$0.15 / 1M  (GPT-4o mini input)
#   Output ~$0.60 / 1M  (GPT-4o mini output)
UI_COST_PER_1M_INPUT  = float(os.getenv("UI_COST_PER_1M_INPUT",  "0.15"))
UI_COST_PER_1M_OUTPUT = float(os.getenv("UI_COST_PER_1M_OUTPUT", "0.60"))

# Answer-style presets shown in the sidebar temperature selector.
UI_TEMP_OPTIONS: dict[str, float] = {
    "Precise":      0.1,
    "Balanced":     0.4,
    "Creative":     0.7,
    "Experimental": 1.0,
}
