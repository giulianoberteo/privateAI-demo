# Disclaimer
I'm not an expert in Artificial Intelligence, LLMs, RAG, MCP, or any of the tools and technologies mentioned in this demo.

This is my personal learning experience setting up a fully local RAG & MCP server stack. Your mileage might vary.

My machine is a MacBook Pro M2 Max with 32 GB of RAM, so I had to make some tradeoffs in terms of model size and chunking strategy to avoid running out of memory. If you have more resources available, you can use larger models and bigger chunks for better performance.

All commands and code snippets are based on Apple Silicon with macOS. If you're on a different OS or architecture, adjust accordingly.

---

# Quick Start

```bash
# 1. Install Ollama and pull the models
curl -fsSL https://ollama.com/install.sh | sh
ollama pull mxbai-embed-large
ollama pull qwen3.5:35b-a3b

# 2. Install uv and set up the project
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env   # restart shell or source the env
uv sync                        # installs all dependencies from pyproject.toml

# 3. Place your VCF PDFs in rag/contentData/ and ingest them
uv run rag/ingestData.py

# 4a. Run the Streamlit UI
uv run streamlit run ui/ui-app.py

# 4b. Or start the MCP server (for Claude Desktop / Cherry Studio / etc.)
uv run mcp/server.py
```

---

# System Architecture

This project implements a 100% Local Retrieval-Augmented Generation (RAG) architecture. Every component — from text extraction to vector storage and language model inference — runs entirely on the host machine, ensuring absolute data locality.

The architecture is split into three core workflows:

<img src="screenshots/system-architecture.png" alt="System Architecture" width="700"/>

## 1. Offline Data Ingestion & Indexing (The Blue Pipeline)
Before any chat takes place, raw technical data is prepared and stored in a structured format:

- **Document parsing**: `rag/ingestData.py` reads local VCF technical resources (PDF, TXT).
- **Version detection**: the filename is parsed to determine the VCF version (e.g. `9.0`, `9.1`). Each version is stored in its own isolated ChromaDB collection (`docs_vcf90`, `docs_vcf91`, …) so queries never return conflicting results from two versions simultaneously.
- **Text chunking**: documents are split into semantic, manageable text blocks to fit the embedding model's context window.
- **Vector embeddings via Ollama**: each chunk is sent to the `mxbai-embed-large` model running locally via Ollama. This converts text into high-dimensional mathematical vectors representing technical intent.
- **Storage**: vectors, alongside metadata (`source`, `page`, `version`), are saved into a local ChromaDB instance.

## 2. Live Agent Interaction & RAG Workflow (The Green Pipeline)
When a user asks a question via the frontend:

- **User query** → submitted via the Streamlit UI (`ui/ui-app.py`).
- **Version selection** → the UI sidebar lets you pin to a specific VCF version. The query only touches that version's collection.
- **Local vector search** → the question is converted to a vector and ChromaDB returns the top matching document chunks in milliseconds.
- **Contextual synthesis** → the original question + retrieved snippets are packaged into an augmented prompt.
- **Local inference via Ollama** → dispatched to `qwen3.5:35b-a3b` running locally; response streamed token-by-token back to the UI.

## 3. Extensible Multi-App Gateway (The Orange/Brown Pathway)
Beyond the custom web interface, the knowledge base is also exposed via the Model Context Protocol (MCP):

- **FastMCP Integration**: `mcp/server.py` wraps ChromaDB as a standardised MCP tool (`search_vcf_documentation`). The tool accepts a `version` parameter so the calling LLM can target a specific VCF release or call it twice for cross-version comparisons.
- **Third-party agnostic**: any MCP-compliant client (Claude Desktop, Cherry Studio, Perplexity, etc.) can bind to this local server, letting you swap frontends while keeping the data pipelines and vector stores intact.

---

# Part 1: Prepare the Engine

## Install Ollama
```shell
curl -fsSL https://ollama.com/install.sh | sh
```

## Pull the models

Two models work together here — a **Librarian** (embeddings) and a **Brain** (reasoning):

```shell
# The Librarian — converts text to vectors for semantic search
ollama pull mxbai-embed-large

# The Brain — reasons over retrieved context and generates answers
ollama pull qwen3.5:35b-a3b
```

> **Optional upgrade:** `bge-m3` is the current best-in-class local embedding model for large technical libraries (8k context window, hybrid dense+sparse retrieval). See [Considerations](#considerations-and-next-steps) for how to switch.

---

# Part 2: Setup the Project

Install uv (fast Python package manager):
```shell
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Restart the shell session, or run:
```shell
source $HOME/.local/bin/env          # sh, bash, zsh
source $HOME/.local/bin/env.fish     # fish
```

Clone or create the project folder:
```shell
git clone <repo-url> privateAI-demo
cd privateAI-demo
uv python pin 3.12
```

Install all dependencies in one command (reads from `pyproject.toml`):
```shell
uv sync
```

> All dependencies — `chromadb`, `fastmcp`, `httpx`, `langchain-text-splitters`, `ollama`, `pymupdf`, `pypdf`, `streamlit`, `tqdm` — are declared in `pyproject.toml` and installed by `uv sync`.

---

# Part 3: Ingest Documents into the Vector DB

## Prepare your documents

Place your VCF PDF files inside `rag/contentData/`. The ingestion script automatically detects the VCF version from the filename:

| File | Detected version | Collection created |
|---|---|---|
| `vmware-cloud-foundation-9.0.pdf` | `9.0` | `docs_vcf90` |
| `vmware-cloud-foundation-9-1.pdf` | `9.1` | `docs_vcf91` |

Both files can be present at the same time — each is routed to its own collection in a single run.

## Run the ingestion

```shell
uv run rag/ingestData.py
```

The script will:
1. Detect VCF version(s) from the filename(s).
2. Create or update the matching ChromaDB collection(s) under `rag/chroma_db/`.
3. Split each document into ~800-character chunks (configurable, see [Configuration](#configuration)).
4. Embed and upsert every chunk via `mxbai-embed-large`. Re-running is safe — upsert is idempotent.
5. Report total chunks indexed on exit.

> See [`rag/ingestData.py`](rag/ingestData.py)

## Verify ingestion

Use the CLI search utility to run a quick vector query without starting the full UI:

```shell
uv run rag/testSearch.py "stretch cluster design decisions"
uv run rag/testSearch.py "NSX configuration" --version 9.1 -n 10
```

---

# Part 4: Create the MCP Server (FastMCP)

`mcp/server.py` is the heart of the project. It wraps the ChromaDB vector store as a standardised MCP tool so any compatible LLM client can query your private VCF documentation.

## Tools exposed

**`search_vcf_documentation(query, version="9.1", n_results=20)`**  
Semantic RAG search across the specified VCF version's documentation. Returns the top `n_results` chunks with source file, page number, and version label.

- Set `version="9.0"` to query the 9.0 library specifically.
- For **cross-version comparison** questions (e.g. *"what changed in 9.1 for stretch clustering?"*), the LLM will automatically call this tool twice — once per version — then synthesise both result sets. No special configuration needed.

**`get_lab_alerts(severity="CRITICAL")`** *(WIP)*  
Fetches live alerts from VCF Operations (Aria Ops) via REST API. Requires `VCF_OPS_URL` and `VCF_OPS_TOKEN` environment variables. See [Configuration](#configuration).

> See [`mcp/server.py`](mcp/server.py)

---

# Part 5: Install Claude Desktop and Connect the MCP Server

```shell
brew install --cask claude
```

## Configure Claude Desktop

Open the configuration file:
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

Add the MCP server entry below, replacing `/Users/YOUR_USERNAME/` with your actual home directory:

```json
{
  "mcpServers": {
    "vcf-docs": {
      "command": "/Users/YOUR_USERNAME/.local/bin/uv",
      "args": [
        "--directory",
        "/Users/YOUR_USERNAME/local-code-repo/privateAI-demo",
        "run",
        "mcp/server.py"
      ]
    }
  }
}
```

> The `--directory` must point to the `privateAI-demo/` project root (where `pyproject.toml` lives) so `uv` picks up the correct virtual environment.

---

# Part 6: Test the RAG in Claude Desktop

Open Claude Desktop and ask questions about VCF documentation. You should see the `vcf-docs` tool being called, with relevant snippets returned as part of the answer.

Screenshots for reference:

Prompt: **List all design decisions that relate to stretch clustering in the VCF fleet with multiple sites across multiple regions blueprint**

![claude-prompt-1](screenshots/claude-prompt-1.png "Claude Prompt 1")

Prompt: **Provide me with the source references that you used to answer the design decisions that relate to stretch clustering in the VCF fleet with multiple sites across multiple regions blueprint**

![claude-prompt-2-references](screenshots/claude-prompt-2-references.png "Claude Prompt 2 - References")

Prompt: **are you getting this information from the internet ?**

![claude-prompt-3-references](screenshots/claude-prompt-3-sources.png "Claude Prompt 3 - Sources")

---

# Part 7: Streamlit UI (standalone, no Claude Desktop required)

The Streamlit app provides a full chat interface that talks directly to ChromaDB and Ollama — no internet, no external API calls.

```shell
uv run streamlit run ui/ui-app.py
```

## Features

- **Version selector** in the sidebar — pin to VCF 9.0 or 9.1 (or any version you've ingested). Switching version automatically clears the chat history to prevent cross-version context bleed.
- **Dynamic model list** — the Brain dropdown is populated live from `ollama list`, so any model you've pulled appears automatically.
- **Temperature slider** — lower values (0.0–0.1) produce more deterministic, factual answers; higher values allow more creative synthesis.
- **Clear Chat button** — resets the conversation without restarting the server.
- **Full conversation memory** — the complete message history is passed to Ollama on every turn, so follow-up questions work correctly.
- **VMware Clarity theme** — dark/light colour scheme built on the Clarity Design System construction palette with Metropolis typography. Toggle between modes with the sidebar button.

### How it works

1. **Streamlit** (`ui-app.py`) coordinates the whole thing.
2. **mxbai-embed-large** + **ChromaDB** — the Librarian — finds the right pages.
3. **qwen3.5:35b-a3b** — the Brain — synthesises the answer using the retrieved context.
4. **M2 Max GPU / Unified Memory** — provides the raw compute for local inference.

### Why this is different from Claude Desktop / ChatGPT

With Claude Desktop or ChatGPT, your data is sent to Anthropic's or OpenAI's servers for reasoning.

With the Streamlit demo, the data never leaves your machine. If you turned off Wi-Fi right now, the reasoning would still work perfectly.

---

# Configuration

All tuneable parameters live in [`config.py`](config.py) at the project root. Every value can be overridden with an environment variable — no code changes needed.

| Environment variable | Default | Purpose |
|---|---|---|
| `EMBED_MODEL` | `mxbai-embed-large` | Ollama embedding model |
| `LLM_MODEL` | `qwen3.5:35b-a3b` | Ollama reasoning model (UI default) |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama API base URL |
| `DEFAULT_VERSION` | `9.1` | VCF version searched when none is specified |
| `NUM_CTX` | `32768` | Ollama context window size (tokens) |
| `CHUNK_SIZE` | `800` | Characters per ingestion chunk |
| `CHUNK_OVERLAP` | `100` | Overlap between consecutive chunks |
| `BATCH_LIMIT` | `20` | Max chunks per ChromaDB upsert batch |
| `DEFAULT_N` | `20` | Default number of results returned by RAG |
| `VCF_OPS_URL` | *(lab default)* | Aria Ops API endpoint (for `get_lab_alerts`) |
| `VCF_OPS_TOKEN` | *(unset)* | Base64 `user:pass` for Aria Ops auth |

Example — switch the embedding model for a single ingest run without editing any file:

```shell
EMBED_MODEL=bge-m3 uv run rag/ingestData.py
```

---

# Considerations and Next Steps

Fine-tuning how data is ingested and which models are used is always the most critical part of any RAG project.

Standard 800-character chunks can be too granular — causing the AI to lose the high-level context of complex multi-step configurations. Upgrading the embedding engine to **BGE-M3** addresses this.

## Why BGE-M3 is the recommended upgrade

- **Native 8,192-token context window** — ingests entire procedures (e.g. an SDDC Manager upgrade) as a single chunk rather than fragmenting them.
- **Hybrid retrieval (Dense + Sparse)** — doesn't just match meaning (Dense); also performs keyword-style Sparse retrieval to catch specific part numbers, error codes, and CLI flags that other models might miss.
- **Built for large technical libraries** — consistently outperforms `mxbai-embed-large` on recall across 8,000+ page corpora.

## How to switch to BGE-M3

```bash
# 1. Pull the new engine
ollama pull bge-m3

# 2. Delete the existing collections (embeddings are model-specific)
uv run python -c "
import chromadb
db = chromadb.PersistentClient('rag/chroma_db')
for col in db.list_collections():
    db.delete_collection(col.name)
print('All collections deleted.')
"

# 3. Re-ingest using the new model (no code changes needed)
EMBED_MODEL=bge-m3 uv run rag/ingestData.py
```

The Streamlit UI and MCP server will pick up `EMBED_MODEL=bge-m3` automatically if you add it to your shell environment or a `.env` file.

## Multi-version support

The project is designed to grow with new VCF releases. To add a future version (e.g. 9.2):

1. Add one entry to `VERSION_MAP` in `config.py`:
   ```python
   VERSION_MAP = {
       "9.0": "docs_vcf90",
       "9.1": "docs_vcf91",
       "9.2": "docs_vcf92",   # ← add this
   }
   ```
2. Place the new PDF in `rag/contentData/` and run `uv run rag/ingestData.py`.

The UI version selector and MCP tool version parameter will include the new version automatically.
