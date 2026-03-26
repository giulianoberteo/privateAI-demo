# Step 1: Prepare the engine
## Install Ollama
```shell
curl -fsSL https://ollama.com/install.sh | sh
```

## Pull the models.
Initially, I used the simplest llama3. Later, while doing further testing, switched to qwen2.5:32b, which does provide better reasoning, and 32B parameters (~19GB disk space required, and also RAM)
```shell
ollama pull llama3
ollama pull nomic-embed-text
```
I ended up switching to a better model for larger pages and documents. The following model replaces nomic-embed-text
```shell
ollama pull qwen2.5:32b
ollama pull mxbai-embed-large
```

# Step 2: Setup the project
## Install uv (fast Python manager)
```shell
curl -LsSf https://astral.sh/uv/install.sh | sh
```
Restart the shell session, or alternatively run
```shell
source $HOME/.local/bin/env (sh, bash, zsh)
source $HOME/.local/bin/env.fish (fish) 
```
Create the project folder
```shell
mkdir rag
cv rag
uv init
uv python pin 3.12
```

Update pyproject.toml to specify to use Python 3.12 we just installed, as following:
```toml
[project]
name = "rag"
version = "0.1.0"
description = "Giuliano Bertello Private AI RAG Demo"
readme = "README.md"
requires-python = ">=3.12"
dependencies = []
```

Now we can re-run the command to add the chromadb inside the RAG project folder
```shell
uv add fastmcp chromadb ollama
uv add pypdf langchain-text-splitters
````
Alternatively to handle documents with thousands of pages, best to use PyMuPDF (fitz). It is written in C, and it is roughly 20x to 50x faster than pypdf
```shell
uv add pymupdf
```

# Step 3: Create the Python ingestion tinto Vectors "maps"
This is required to ingest the document that we want the RAG to index into ChromaDB. Each paragraph get assigned a vector "index map"
See [rag](ingestData.py)

The script uses "Recursive Chunking". By simply dumping a whole 50-page configuration guide into the AI, it will likely "hallucinate" or miss details. By chunking, we turn the documents into a massive searchable map.
- Chunk Size (1000): We cut the text into 1000-character blocks.
- Overlap (100): We keep 100 characters from the previous block at the start of the next one. This ensures that if a sentence like "To configure the VCF9 license, click here" gets cut in half, the context exists in both chunks.

add a progress bar and run once the ingestion script
```shell
uv add tqdm
uv run ingestData.py
```
# Step 4: Create the MCP server (FastMCP)
server.py content here

# Step 5: download and install Claude Desktop
```shell
brew install --cask claude
```
## Configure Claude Desktop to point to the local RAG
Open your terminal and find your exact folder path by typing: pwd (Copy this path).

Open Claude Desktop's configuration file. You can usually do this from the Claude menu bar: Claude > Settings > Developer > Edit Config, or by opening ~/Library/Application Support/Claude/claude_desktop_config.json.

```json
{
  "preferences": {
    "coworkWebSearchEnabled": true,
    "ccdScheduledTasksEnabled": false,
    "coworkScheduledTasksEnabled": false
  },
  "mcpServers": {
    "docs": {
      "command": "/Users/gb003139/.local/bin/uv",
      "args": [
        "--directory",
        "/Users/gb003139/SynologyDrive/DropBox/code/privateAI-demo/rag",
        "run",
        "server.py"
      ]
    }
  }
}
```
# Step N: consider indexing using a different model
The "Pro" Alternative: bge-m3
If you find that 800-character chunks are too small (meaning the AI loses the "big picture" of a configuration step), you should switch to bge-m3.

In 2026, bge-m3 is the gold standard for your M2 Max because:

Massive Context: It has an 8,192 token limit (like Nomic). You won't get "400 Bad Request" errors ever again.

High Accuracy: It matches or beats mxbai in technical retrieval.

Multi-Function: It is designed specifically for "Dense" retrieval like your VCF encyclopedia.

How to switch to BGE-M3:
Pull the model: ollama pull bge-m3

Delete the DB: rm -rf chroma_db

Update ingestData.py and server.py:
