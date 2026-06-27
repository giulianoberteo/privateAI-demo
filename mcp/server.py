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

_collection_cache: dict = {}


def _get_collection(version: str):
    """Return the ChromaDB collection for the requested VCF version (cached)."""
    if version in _collection_cache:
        return _collection_cache[version]
    if version not in config.VERSION_MAP:
        available = ", ".join(sorted(config.VERSION_MAP))
        raise ValueError(f"Unknown version '{version}'. Available: {available}")
    col_name = config.VERSION_MAP[version]
    try:
        col = _chroma.get_collection(name=col_name, embedding_function=_emb_fn)
        _collection_cache[version] = col
        return col
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
    twice — once per version — then synthesise the two result sets.

    Args:
        query:     Technical question or topic to search.
        version:   VCF version to query. Defaults to the configured default version.
                   Check config.VERSION_MAP for available versions.
        n_results: Number of chunks to retrieve (default from config, max 50).
    """
    collection = _get_collection(version)
    n_results  = max(1, min(n_results, 50))

    results = collection.query(
        query_texts=[f"{config.QUERY_PREFIX}{query}"],
        n_results=n_results,
    )

    docs  = results["documents"][0]
    metas = results["metadatas"][0]
    dists = results["distances"][0]

    output = []
    for text, meta, dist in zip(docs, metas, dists):
        if dist > config.MAX_DISTANCE:
            continue
        source = meta.get("source", "unknown")
        page   = meta.get("page", "?")
        ver    = meta.get("version", version)
        output.append(f"[VCF {ver} | {source} | Page {page}]\n{text}")

    # If the distance threshold filtered everything, fall back to the closest match
    if not output and docs:
        meta = metas[0]
        output.append(
            f"[VCF {meta.get('version', version)} | {meta.get('source', 'unknown')} "
            f"| Page {meta.get('page', '?')}]\n{docs[0]}"
        )

    return "\n\n---\n\n".join(output)


# --- Aria Ops token cache (acquired once per server lifetime) ---
_ops_token: str = ""


async def _acquire_ops_token(base_url: str, user: str, password: str) -> str:
    """POST to Aria Ops token endpoint and cache the result."""
    global _ops_token
    if _ops_token:
        return _ops_token
    # authSource is the display name of the auth source in Aria Ops (not the type ID).
    # For local accounts omit it entirely; for LDAP set VCF_OPS_AUTH_SOURCE to the
    # exact auth source name shown in Aria Ops Administration > Auth Sources.
    auth_source = os.getenv("VCF_OPS_AUTH_SOURCE", "")
    body: dict = {"username": user, "password": password}
    if auth_source:
        body["authSource"] = auth_source
    async with httpx.AsyncClient(verify=False) as http:  # noqa: S501
        resp = await http.post(
            f"{base_url}/suite-api/api/auth/token/acquire",
            json=body,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        _ops_token = resp.json()["token"]
        return _ops_token


# --- Tool 2: VCF Operations live alerts ---
@mcp.tool()
async def get_lab_alerts(severity: str = "") -> str:
    """Fetch live alerts from the VCF Operations (Aria Ops) lab.

    Credentials are read from environment variables — set them in
    claude_desktop_config.json under the "env" key for this MCP server:
      VCF_OPS_URL  — Aria Ops base URL, e.g. https://vcf-ops.lab.local
      VCF_OPS_USER — Aria Ops username, e.g. admin@local
      VCF_OPS_PASS — Aria Ops password

    Args:
        severity: Alert criticality filter. One of: CRITICAL, IMMEDIATE, WARNING,
                  INFORMATION. Leave empty (default) to return all active alerts
                  regardless of severity.
    """
    # Read connection details and credentials from environment variables.
    # These are injected by Claude Desktop from the "env" block in claude_desktop_config.json.
    base_url = os.getenv("VCF_OPS_URL", "https://vcf-ops.lab.local")
    user     = os.getenv("VCF_OPS_USER", "")
    password = os.getenv("VCF_OPS_PASS", "")
    token    = os.getenv("VCF_OPS_TOKEN", "")  # fallback: pre-acquired Base64 Basic token

    # Bail out early if no credentials are configured at all.
    if not user and not token:
        return (
            "No credentials found. Set VCF_OPS_USER + VCF_OPS_PASS "
            "(recommended) or VCF_OPS_TOKEN."
        )

    # verify=False because lab Aria Ops uses a self-signed TLS certificate.
    async with httpx.AsyncClient(verify=False) as http:  # noqa: S501
        try:
            # --- Step 1: Authenticate ---
            # Preferred: exchange username + password for a short-lived OpsToken.
            # Fallback: use a pre-encoded Basic token set in VCF_OPS_TOKEN.
            if user:
                try:
                    ops_token = await _acquire_ops_token(base_url, user, password)
                except httpx.HTTPStatusError as e:
                    return (
                        f"Token acquisition failed — HTTP {e.response.status_code}.\n"
                        f"URL: {e.request.url}\n"
                        f"Response: {e.response.text[:500]}"
                    )
                headers = {"Authorization": f"OpsToken {ops_token}", "Accept": "application/json"}
            else:
                headers = {"Authorization": f"Basic {token}", "Accept": "application/json"}

            # --- Step 2: Fetch alerts ---
            # Without a severity filter the API returns all active alerts.
            # With a filter it returns only alerts matching that criticality level.
            url = f"{base_url}/suite-api/api/alerts"
            if severity:
                url += f"?alertCriticality={severity.upper()}"
            response = await http.get(url, headers=headers)
            response.raise_for_status()

            data       = response.json()
            raw_alerts = data.get("alerts", [])

            if not raw_alerts:
                label = severity.upper() if severity else "active"
                return f"No {label} alerts found."

            # --- Step 3: Resolve resource names ---
            # Aria Ops alert objects contain only a resourceId (UUID), not a
            # human-readable name. We call GET /resources/{id} for each unique
            # resource in the top-5 alerts to get the display name.
            # Results are cached so the same resource is never fetched twice.
            resource_cache: dict[str, str] = {}
            for a in raw_alerts[:5]:
                rid = a.get("resourceId", "")
                if rid and rid not in resource_cache:
                    try:
                        r = await http.get(
                            f"{base_url}/suite-api/api/resources/{rid}",
                            headers=headers,
                        )
                        if r.status_code == 200:
                            # resourceKey.name holds the object's display name
                            # (e.g. "esxi-01.lab.local" or "my-vm")
                            resource_cache[rid] = (
                                r.json().get("resourceKey", {}).get("name", rid)
                            )
                        else:
                            resource_cache[rid] = rid  # fall back to the raw ID
                    except Exception:
                        resource_cache[rid] = rid

            # --- Step 4: Format output ---
            lines = []
            for a in raw_alerts[:5]:
                rid      = a.get("resourceId", "")
                resource = resource_cache.get(rid, rid or "unknown-resource")
                # alertDefinitionName is the standard field; fall back to older field names
                # used by some Aria Ops versions.
                name = (
                    a.get("alertDefinitionName")
                    or a.get("alertName")
                    or a.get("type", "unknown-alert")
                )
                lines.append(f"- {resource}: {name}")

            return "\n".join(lines)

        except httpx.HTTPStatusError as e:
            return (
                f"Alerts request failed — HTTP {e.response.status_code}.\n"
                f"URL: {e.request.url}\n"
                f"Response: {e.response.text[:500]}"
            )
        except Exception as e:
            return f"Error connecting to VCF Operations: {type(e).__name__}: {e}"


if __name__ == "__main__":
    mcp.run()
