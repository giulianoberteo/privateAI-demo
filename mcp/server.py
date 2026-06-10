"""
VCF Assistant: Local MCP Server for Documentation RAG & Lab Operations.

Each VCF version lives in its own ChromaDB collection (docs_vcf90, docs_vcf91, …).
The search tool accepts an explicit version parameter so the LLM always queries
a single, unambiguous collection — eliminating conflicting cross-version results.

For comparison questions ("what changed between 9.0 and 9.1?") the LLM calls
the tool twice — once per version — then synthesises both clean result sets.

CAPABILITIES:
1. search_vcf_documentation — RAG over a specific VCF version's documentation.
2. get_lab_alerts            — Live alerts from VCF Operations (Aria Ops) via REST (WIP).

INFRASTRUCTURE:
- Framework: FastMCP (Model Context Protocol)
- Database: ChromaDB (Local Persistent Client, versioned collections)
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

mcp = FastMCP("VCF-Assistant")

# Shared client and embedding function — opened once, reused across all tool calls.
try:
    _chroma = chromadb.PersistentClient(path=str(config.DB_PATH))
    _emb_fn = embedding_functions.OllamaEmbeddingFunction(
        model_name=config.EMBED_MODEL,
        url=f"{config.OLLAMA_URL}/api/embeddings",
    )
except Exception as e:
    raise RuntimeError(
        f"Failed to initialise ChromaDB at {config.DB_PATH}.\n"
        f"Run rag/ingestData.py first to build the index.\nOriginal error: {e}"
    ) from e


def _get_collection(version: str):
    """Return the ChromaDB collection for the requested VCF version."""
    if version not in config.VERSION_MAP:
        available = ", ".join(sorted(config.VERSION_MAP))
        raise ValueError(f"Unknown version '{version}'. Available: {available}")
    col_name = config.VERSION_MAP[version]
    try:
        return _chroma.get_collection(name=col_name, embedding_function=_emb_fn)
    except Exception:
        raise ValueError(
            f"Collection '{col_name}' for VCF {version} does not exist. "
            f"Run rag/ingestData.py with the VCF {version} PDF in contentData/ to build it."
        )


# --- Tool 1: Search VCF Documentation ---
@mcp.tool()
def search_vcf_documentation(
    query: str,
    version: str = config.DEFAULT_VERSION,
    n_results: int = config.DEFAULT_N,
) -> str:
    """Search the VCF documentation for a specific version.

    Each version is stored in its own isolated collection, so results are
    guaranteed to contain only content from the requested version.

    For comparison questions (e.g. "what changed in 9.1?"), call this tool
    twice — once with version='9.0' and once with version='9.1' — then
    synthesise the two result sets.

    Args:
        query:     Technical question or topic to search.
        version:   VCF version to query. Available: 9.0, 9.1. Defaults to 9.1.
        n_results: Number of chunks to retrieve (default 20, max 50).
    """
    collection = _get_collection(version)
    n_results  = min(n_results, 50)

    results = collection.query(
        query_texts=[f"{config.QUERY_PREFIX}{query}"],
        n_results=n_results,
    )

    output = []
    for text, meta in zip(results["documents"][0], results["metadatas"][0]):
        source = meta.get("source", "unknown")
        page   = meta.get("page", "?")
        ver    = meta.get("version", version)
        output.append(f"[VCF {ver} | {source} | Page {page}]\n{text}")

    return "\n\n---\n\n".join(output)


# --- Tool 2: VCF Operations live alerts (WIP) ---
@mcp.tool()
async def get_lab_alerts(severity: str = "CRITICAL") -> str:
    """Fetch live alerts from the VCF Operations (Aria Ops) lab.

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
