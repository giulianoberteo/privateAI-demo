"""
VCF 9 Assistant: Local MCP Server for Documentation RAG & Lab Operations.

This server acts as a bridge between LLMs and local VCF 9 documentation.

CORE CAPABILITIES:
1. Retrieval Augmented Generation (RAG):
   Performs semantic vector searches across an 8,000+ page VCF 9 technical
   library stored in a local ChromaDB instance.

2. Live Infrastructure Monitoring (WIP):
   Integrates with VCF Operations (Aria Ops) via REST API to pull real-time
   critical alerts. Configure via VCF_OPS_URL and VCF_OPS_TOKEN env vars.

INFRASTRUCTURE:
- Framework: FastMCP (Model Context Protocol)
- Database: ChromaDB (Local Persistent Client)
- Embeddings: Ollama API (Local)
"""

import os
import sys
import httpx  # pyright: ignore[reportMissingImports]
import chromadb  # pyright: ignore[reportMissingImports]
from fastmcp import FastMCP  # pyright: ignore[reportMissingImports]
from chromadb.utils import embedding_functions  # pyright: ignore[reportMissingImports]
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # pyright: ignore[reportMissingImports]

mcp = FastMCP("VCF9-Assistant")

# --- DB connection (fail fast with a clear message if DB is missing) ---
try:
    _client = chromadb.PersistentClient(path=str(config.DB_PATH))
    _emb_fn = embedding_functions.OllamaEmbeddingFunction(
        model_name=config.EMBED_MODEL,
        url=f"{config.OLLAMA_URL}/api/embeddings",
    )
    collection = _client.get_collection(name=config.COLLECTION, embedding_function=_emb_fn)
except Exception as e:
    raise RuntimeError(
        f"Failed to open ChromaDB collection '{config.COLLECTION}' at {config.DB_PATH}.\n"
        f"Run rag/ingestData.py first to build the index.\nOriginal error: {e}"
    ) from e


# --- Tool 1: Search VCF Documentation ---
@mcp.tool()
def search_vcf_documentation(query: str, n_results: int = config.DEFAULT_N) -> str:
    """Search the 8,000+ page VCF 9 documentation for specific technical answers.

    Args:
        query: The technical question or topic to search for.
        n_results: Number of document chunks to retrieve (default 20, max 50).
    """
    n_results = min(n_results, 50)  # Hard cap to avoid overwhelming the LLM
    instructional_query = f"{config.QUERY_PREFIX}{query}"

    results = collection.query(query_texts=[instructional_query], n_results=n_results)

    output = []
    for text, meta in zip(results["documents"][0], results["metadatas"][0]):
        source = meta.get("source", "unknown")
        page   = meta.get("page", "?")
        output.append(f"[{source} | Page {page}]\n{text}")

    return "\n\n---\n\n".join(output)


# --- Tool 2: VCF Operations live alerts (WIP) ---
@mcp.tool()
async def get_lab_alerts(severity: str = "CRITICAL") -> str:
    """Fetch live alerts directly from the VCF 9 Operations (Aria Ops) lab.

    Requires VCF_OPS_URL and VCF_OPS_TOKEN environment variables.
    """
    vcf_ops_url = os.getenv("VCF_OPS_URL", "https://vcf-ops.lab.local/suite-api/api/alerts")
    token       = os.getenv("VCF_OPS_TOKEN", "")

    if not token:
        return "VCF_OPS_TOKEN env var is not set — cannot authenticate to VCF Operations."

    headers = {"Authorization": f"Basic {token}", "Accept": "application/json"}

    async with httpx.AsyncClient(verify=False) as http:
        try:
            response = await http.get(f"{vcf_ops_url}?severity={severity}", headers=headers)
            response.raise_for_status()
            data   = response.json()
            alerts = [
                f"- {a['resourceName']}: {a['alertName']}"
                for a in data.get("alerts", [])[:5]
            ]
            return "\n".join(alerts) if alerts else "No critical alerts found."
        except Exception as e:
            return f"Error connecting to VCF Lab: {e}"


if __name__ == "__main__":
    mcp.run()
