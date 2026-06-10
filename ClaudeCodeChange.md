# Claude Code Changes — privateAI-demo

**Date:** 2026-06-10  
**Commit:** `1e9945b`  
**Branch:** `main`

---

## Overview

Full review of the codebase: README, all Python scripts, and `pyproject.toml`.  
Six files changed across four concerns: shared configuration, ingestion robustness, MCP server improvements, and UI correctness.

---

## 1. New File — `config.py`

**What:** Centralised configuration module at the project root.

**Why:** The embedding model name `"mxbai-embed-large"` was hard-coded in three separate files (`ingestData.py`, `server.py`, `ui-app.py`). Changing the model (e.g. upgrading to `bge-m3`) required editing every file individually and risked drift. The Ollama URL, ChromaDB path, chunk sizes, and number of retrieval results suffered the same problem.

**What it does:**
- Exposes `EMBED_MODEL`, `LLM_MODEL`, `OLLAMA_URL`, `DB_PATH`, `COLLECTION`, `QUERY_PREFIX`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `BATCH_LIMIT`, `DEFAULT_N`, and `NUM_CTX` as module-level constants.
- Every constant is overridable via a matching environment variable (e.g. `EMBED_MODEL=bge-m3 uv run ingestData.py`).
- All other scripts now import this module via `sys.path` insertion.

---

## 2. `rag/ingestData.py`

### Fix: `collection.add()` → `collection.upsert()`

**What:** Replaced all calls to `collection.add()` with `collection.upsert()`.

**Why (bug):** ChromaDB raises an error if you call `add()` with a document ID that already exists in the collection. Since the IDs are deterministic (`{stem}_p{page}_c{chunk}`), running the ingestion script a second time on the same PDFs would always crash. `upsert()` inserts new documents and silently overwrites existing ones, making re-runs idempotent.

---

### Fix: Path resolved via `Path(__file__)`

**What:** Replaced `path="./chroma_db"` with `Path(__file__).resolve().parent / "chroma_db"`.

**Why:** A relative path is resolved against the current working directory at runtime. The script only worked correctly when invoked from inside the `rag/` folder. Using `__file__` makes the path absolute and correct regardless of where the script is run from.

---

### Enhancement: TXT file support

**What:** Added `data_dir.glob("*.txt")` alongside `*.pdf`; TXT files are read as a single page via `Path.read_text()`.

**Why:** The README listed TXT as a supported document type but the code only handled PDF. This brings the implementation in line with the documented capability without adding any new dependency.

---

### Fix: Final batch flush now inside a try/except

**What:** Extracted the flush logic into a `flush_batch()` helper that handles both mid-loop and end-of-file flushes uniformly.

**Why:** The original code wrapped mid-loop batches in `try/except` but the final flush (after the `for` loop) was unguarded. An Ollama error on the last batch would produce an unhandled exception with no hint about the cause.

---

### Enhancement: Ingestion summary at exit

**What:** Counts total chunks upserted and prints them at completion.

**Why:** The original success message gave no indication of how many chunks were indexed, making it hard to spot issues (e.g. a document producing zero chunks due to encoding problems).

---

## 3. `mcp/server.py`

### Enhancement: `n_results` parameter on `search_vcf_documentation`

**What:** Added `n_results: int = config.DEFAULT_N` as an explicit tool parameter (hard-capped at 50).

**Why:** The result count was hard-coded to 20. MCP callers (Claude Desktop, Cherry Studio, etc.) had no way to request a broader or narrower search. Exposing it as a parameter gives the calling LLM control over recall depth.

---

### Enhancement: Source filename included in each result

**What:** Each result entry now reads `[{source} | Page {page}]` instead of `[Page {page}]`.

**Why:** When the vector store contains multiple documents, the page number alone is ambiguous. The source filename tells the LLM (and the end user) which document the snippet came from.

---

### Fix: Lab credentials moved to environment variables

**What:** `VCF_OPS_URL` and `VCF_OPS_TOKEN` are now read from `os.getenv()` instead of being hard-coded strings. The tool returns a clear message if `VCF_OPS_TOKEN` is unset.

**Why:** Hard-coded placeholder credentials in source code are a security smell and would be committed to version history. Env vars are the standard pattern for secrets.

---

### Fix: Startup DB init wrapped in `try/except`

**What:** The `chromadb.PersistentClient` and `get_collection()` calls are now inside a `try/except` block that raises a `RuntimeError` with a clear "run ingestData.py first" message.

**Why:** If the ChromaDB collection does not exist (e.g. on a fresh clone before ingestion), the server crashed with a low-level ChromaDB traceback. The new error message directly tells the user what to do.

---

### Fix: Removed unused loop index variable

**What:** Changed `for i, (text, meta) in enumerate(zip(...))` to `for text, meta in zip(...)`.

**Why:** The index `i` was never used. IDE flagged it as a hint; removing it keeps the code clean.

---

## 4. `ui/ui-app.py`

### Critical Fix: Conversation history now passed to `ollama.chat()`

**What:** `ollama.chat()` now receives the full `st.session_state.messages` history prepended by the system prompt, instead of only the current user message.

**Why (critical bug):** The original code constructed the Ollama message list as:
```python
messages=[
    {'role': 'system', 'content': system_prompt},
    {'role': 'user',   'content': prompt}
]
```
This means the model had **no memory of any previous turn**. Every question was answered as if it were the first message in the conversation. Multi-turn follow-up questions ("expand on that", "what about X?") would fail to reference earlier answers. The fix appends the entire session state so the model sees the complete dialogue.

---

### Performance Fix: `num_ctx=32768` added to Ollama options

**What:** Added `"num_ctx": config.NUM_CTX` (default 32 768 tokens) to `ollama.chat()` options.

**Why:** With 25 retrieved chunks of ~800 characters each (~20 000 characters of context) plus conversation history, the default Ollama context window for some models can be too small, causing silent truncation. Setting `num_ctx` explicitly ensures the full RAG context fits.

---

### Enhancement: Dynamic model list from `ollama.list()`

**What:** Replaced the hardcoded `["qwen3.5:35b-a3b", "qwen2.5:32b"]` selectbox with a `get_available_models()` function that calls `ollama.list()` at startup (cached for 30 seconds). Falls back to the defaults if Ollama is unreachable.

**Why:** The hardcoded list would not reflect models the user had actually pulled. If the default model was not installed, the UI would silently send requests to a non-existent model.

---

### Enhancement: Clear Chat button

**What:** Added a "Clear Chat" button to the sidebar that resets `st.session_state.messages` and calls `st.rerun()`.

**Why:** There was no way to start a fresh conversation without restarting the Streamlit server.

---

### Fix: Friendly error when ChromaDB is missing

**What:** `init_db()` is now wrapped in `try/except`; on failure it calls `st.error()` with a user-readable message and `st.stop()`.

**Why:** A missing or corrupt ChromaDB collection previously caused an unhandled exception that crashed the entire Streamlit page with a Python traceback visible to the user.

---

### Fix: Source deduplication preserves retrieval order

**What:** Changed `for s in set(source_list)` to `for s in dict.fromkeys(source_list)`.

**Why:** `set()` returns elements in an arbitrary (hash-based) order, losing the relevance ranking from ChromaDB. `dict.fromkeys()` deduplicates while preserving the original insertion order (guaranteed in Python 3.7+).

---

## 5. `rag/testSearch.py`

### Fix: Path resolved via `Path(__file__)`

**What:** Replaced `"../rag/chroma_db"` with `Path(__file__).resolve().parent / "chroma_db"`.

**Why:** The old relative path was resolved against the process CWD. Running the script from outside the `rag/` directory produced a "collection not found" error. The `__file__`-based path is always correct.

---

### Enhancement: Shared config constants

**What:** Imports `config` for `EMBED_MODEL`, `OLLAMA_URL`, `COLLECTION`, and `QUERY_PREFIX`.

**Why:** Consistency — if you change the embedding model via the env var, `testSearch.py` now picks up the same model automatically.

---

### Enhancement: Improved output formatting

**What:** Each result now shows `[{i}] {source} (Page {page})` on its own line before the snippet, and the search header reports the model in use.

**Why:** The original output only showed the source and page inline with the text, making it harder to scan multiple results quickly.

---

## 6. `pyproject.toml`

### Fix: Added `httpx` as an explicit dependency

**What:** Added `"httpx>=0.27.0"` to the dependencies list.

**Why:** `mcp/server.py` imports `httpx` directly for the `get_lab_alerts` tool. It was not listed as a dependency — it worked only because `fastmcp` happens to pull it in transitively. Relying on transitive dependencies is fragile; a future `fastmcp` update that drops `httpx` would break the server silently.
