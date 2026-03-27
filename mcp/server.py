"""
VCF 9 Assistant: Local MCP Server for Documentation RAG & Lab Operations.

This server acts as a bridge between Large Language Models (LLMs) 
and local VCF9 documentation. 

CORE CAPABILITIES:
1. Retrieval Augmented Generation (RAG): 
   Performs semantic vector searches across an 8,000+ page VCF 9 technical 
   library stored in a local ChromaDB instance. Uses the 'mxbai-embed-large' 
   model via Ollama for high-precision technical query matching.

2. Live Infrastructure Monitoring (WIP): - !!! work in progress, need to develop further this section !!!
   Integrates with VCF Operations (Aria Ops) via REST API to pull real-time 
   critical alerts and system health status directly into the chat context.

INFRASTRUCTURE:
- Framework: FastMCP (Model Context Protocol)
- Database: ChromaDB (Local Persistent Client)
- Embeddings: Ollama API (Local)
"""

import httpx # pyright: ignore[reportMissingImports]
import chromadb # pyright: ignore[reportMissingImports]
from fastmcp import FastMCP # pyright: ignore[reportMissingImports]
from chromadb.utils import embedding_functions # pyright: ignore[reportMissingImports]
from pathlib import Path

# 1. Initialize the MCP Server
mcp = FastMCP("VCF9-Assistant")

# 2. Navigate up from /mcp, then down into /rag/chroma_db
# __file__ is server.py. parent is /mcp. parent.parent is /privateAI-demo.
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "rag" / "chroma_db"

# 3. Connect to the existing ChromaDB database
client = chromadb.PersistentClient(path=str(DB_PATH))
emb_fn = embedding_functions.OllamaEmbeddingFunction(
    model_name="mxbai-embed-large",
    url="http://localhost:11434/api/embeddings",
)
collection = client.get_collection(name="docs", embedding_function=emb_fn)

# --- TOOL 1: THE SEARCH (RAG) ---
@mcp.tool()
def search_vcf_documentation(query: str) -> str:
    """Search the 8,000+ page VCF9 documentation for specific technical answers."""
    # MANDATORY: Mxbai needs this specific instruction prefix to work correctly
    instructional_query = f"Represent this sentence for searching relevant passages: {query}"
    
    results = collection.query(query_texts=[instructional_query], n_results=20) # Increased to 20 for better recall with Mxbai's smaller chunk size
    
    output = []
    for i in range(len(results['documents'][0])):
        text = results['documents'][0][i]
        page = results['metadatas'][0][i]['page']
        output.append(f"[Page {page}]: {text}")
        
    return "\n\n---\n\n".join(output)

# --- TOOL 2: THE ACTION (VCF9 API) --- not working at the moment - work in progress, need to develop further this section
@mcp.tool()
async def get_lab_alerts(severity: str = "CRITICAL") -> str:
    """Fetch live alerts directly from the VCF9 Operations lab."""
    # Replace with your actual Lab FQDN and Base64 Auth (User:Pass)
    VCF_OPS_URL = "https://vcf-ops.lab.local/suite-api/api/alerts"
    AUTH_HEADER = {"Authorization": "Basic YOUR_BASE64_TOKEN", "Accept": "application/json"}
    
    async with httpx.AsyncClient(verify=False) as client:
        try:
            response = await client.get(f"{VCF_OPS_URL}?severity={severity}", headers=AUTH_HEADER)
            response.raise_for_status()
            data = response.json()
            # Return a summary so the LLM isn't overwhelmed by JSON
            alerts = [f"- {a['resourceName']}: {a['alertName']}" for a in data.get('alerts', [])[:5]]
            return "\n".join(alerts) if alerts else "No critical alerts found."
        except Exception as e:
            return f"Error connecting to VCF Lab: {str(e)}"

if __name__ == "__main__":
    mcp.run()
