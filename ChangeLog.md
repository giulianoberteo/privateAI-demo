# Claude Code Changes — privateAI-demo

---

## Change Set 15 — Suppress all card borders inside chat message bubbles

**Date:** 2026-06-24
**Branch:** `main`
**Commit:** `053a94e`

### What was changed

#### `ui/themes.py`

The previous fix only silenced `stLayoutWrapper`. The global `stVerticalBlockBorderWrapper > div` card rule (background, `1px solid border`, `box-shadow`) was still firing inside `stChatMessage`, producing a visible edge around the collapsed status widget content. Extended the scoped override to also cover `stVerticalBlockBorderWrapper > div` and its hover state when nested inside a chat message, resetting `border`, `box-shadow`, and `background-color` to transparent so no card edges appear within the response bubble.

---

## Change Set 14 — Remove border from "Analysing data..." status widget

**Date:** 2026-06-24
**Branch:** `main`
**Commit:** `2d8b5af`

### What was changed

#### `ui/themes.py`

Changed `border: 1px solid {v['border']}` to `border: none` on the `[data-testid="stStatusWidget"]` rule. The `st.status()` widget that shows "Consulting VCF library…" / "Analysing data…" was rendering with a visible outline that clashed visually inside the chat message bubble.

---

## Change Set 13 — Remove border from chat message layout wrapper

**Date:** 2026-06-24
**Branch:** `main`
**Commit:** `f326d62`

### What was changed

#### `ui/themes.py`

Added a scoped CSS rule that strips `border` and `box-shadow` from `[data-testid="stLayoutWrapper"]` and its immediate child `div` when they appear inside a `[data-testid="stChatMessage"]`. The global `stVerticalBlockBorderWrapper > div` card rule was bleeding into the assistant response bubble's internal layout wrapper, producing a visible edge around the answer content. The new rule is scoped to the chat message context so bordered cards elsewhere in the UI are unaffected.

---

## Change Set 12 — RAG pipeline optimisations, UI resilience, and config consistency

**Date:** 2026-06-24
**Branch:** `main`
**Commit:** `fb15b2d`

### What was changed

#### `config.py`

**`QUERY_PREFIX` now env-var overridable**
Changed from a hardcoded string to `os.getenv("QUERY_PREFIX", "...")`. If you swap `EMBED_MODEL` to a model that doesn't need an instructional prefix (e.g. `bge-m3`, `nomic-embed-text`), set `QUERY_PREFIX=""` to avoid degraded retrieval quality. Comment updated to document this.

**New `MAX_DISTANCE` constant**
Added `MAX_DISTANCE = float(os.getenv("MAX_DISTANCE", "1.0"))`. ChromaDB results whose L2 distance exceeds this threshold are excluded from LLM context, reducing noise from low-relevance chunks. Configurable via env var; a closest-match fallback ensures the LLM always receives at least one result.

---

#### `rag/ingestData.py`

**Removed local `DB_PATH` shadow**
The script was defining its own `DB_PATH = Path(__file__).resolve().parent / "chroma_db"` instead of using `config.DB_PATH`. While both resolved to the same path today, any future change to `config.py` would have silently diverged. Removed the local definition; the ChromaDB client now uses `config.DB_PATH` directly.

---

#### `mcp/server.py`

**Collection handle caching**
`_get_collection()` previously called `_chroma.get_collection()` on every MCP tool invocation. Added `_collection_cache: dict = {}` to cache collection handles by version after the first open, eliminating repeated handle creation on each tool call.

**`n_results` lower bound**
`n_results = min(n_results, 50)` had no lower bound — `n_results=0` would cause a ChromaDB error. Changed to `max(1, min(n_results, 50))`.

**Distance filtering**
`search_vcf_documentation` now unpacks `results["distances"][0]` and skips chunks whose distance exceeds `config.MAX_DISTANCE`. A fallback to the closest match is applied if all results are filtered out, so the LLM always receives at least one chunk.

**Dynamic docstring**
Removed the hardcoded `"Available: 9.0, 9.1"` from the `version` arg description — this would have become stale when adding VCF 9.2 or later. Replaced with a reference to `config.VERSION_MAP`.

**`verify=False` annotation**
Added `# noqa: S501 — lab uses self-signed cert` to the `httpx.AsyncClient` call to document why SSL verification is intentionally disabled.

---

#### `ui/ui-app.py`

**Session state init moved to top**
`messages` and `session_tokens` were initialised after the sidebar block that reads them, making the init effectively dead code on every version-switch rerun. All three session state keys (`theme`, `messages`, `session_tokens`) are now initialised at the very top, before `st.set_page_config`, ensuring they exist for every subsequent reference.

**CSS generation cached**
`build_css(PALETTES[...])` was called on every Streamlit rerun, regenerating ~500 lines of CSS on every user interaction. Wrapped in a `@st.cache_data` function `_get_css(theme_name: str)` keyed on the theme string — the CSS is now built once per theme per session.

**`_TEMP_OPTIONS` promoted to module-level constant**
The temperature options dict was re-created on every rerun inside the sidebar block. Moved to a module-level constant so it is evaluated once at import time.

**Streaming chunk access fixed**
`chunk["message"]["content"]` used dict-style access on `ChatResponse`, a Pydantic object returned by `ollama>=0.4`. This raises `TypeError` at runtime. Changed to the correct attribute access: `chunk.message.content`. (Note: `_chunk_stat` already handled both styles; this aligns the content access to match.)

**Error handling around `ollama.chat()`**
The entire streaming block is now wrapped in `try/except`. If Ollama is unreachable or the model is not pulled, the app renders `st.error()` with an actionable message and returns cleanly rather than showing a raw Python traceback.

**Distance filtering in `get_vcf_context`**
Aligned with the MCP server: unpacks `results["distances"][0]` and excludes chunks above `config.MAX_DISTANCE`. A closest-match fallback ensures the context string is never empty.

**`DEFAULT_N + 5` magic number removed**
The query was fetching `DEFAULT_N + 5` results with no subsequent trimming — the extra 5 were always passed to the LLM. Changed to `config.DEFAULT_N`.

**Dead commented-out code removed**
Removed the `##`-prefixed commented-out lines (`st.divider()`, `st.info()`) that had accumulated in the sidebar block.

---

## Change Set 11 — PDF download links in "Prepare your documents" table

**Date:** 2026-06-24
**Branch:** `main`

### What was changed

#### `README.md`

Linked the two filenames in the "Prepare your documents" table to their direct Broadcom TechDocs PDF download URLs, so readers can grab the files straight from the README.

---

## Change Set 10 — Collapsible code blocks in README

**Date:** 2026-06-24
**Branch:** `main`

### What was changed

#### `README.md`

Wrapped every code block in `<details>`/`<summary>` HTML tags so readers can expand or collapse them on demand. Works natively on GitHub and most Markdown renderers that support inline HTML. No change to the actual commands or content.

---

## Change Set 9 — Wider and taller chat input textarea

**Date:** 2026-06-24
**Branch:** `main`

### What was changed

#### `ui/themes.py`

Set `min-height: 3rem` (≈ 2 visible lines) and `max-height: 8rem` on the chat textarea so it starts taller and auto-grows up to ~4 lines before scrolling. Also forced `width: 100%` on the input wrapper to ensure the field uses the full available width.

---

## Change Set 8 — Remove chat input border

**Date:** 2026-06-24
**Branch:** `main`

### What was changed

#### `ui/themes.py`

Removed the `1px solid` border from `[data-testid="stChatInput"] [data-baseweb="base-input"]`. The textarea now blends cleanly into the bottom bar without a visible box outline.

---

## Change Set 7 — Default light theme & button visibility fix

**Date:** 2026-06-24
**Branch:** `main`

### What was changed

#### `ui/ui-app.py`

**Default theme changed to light**
`st.session_state.theme` now initialises to `"light"` instead of `"dark"`. First-time visitors land in the light palette without needing to toggle.

#### `ui/themes.py`

**Button border added for visibility**
All `.stButton > button` elements now carry `border: 1px solid {accent} !important` instead of `border: none`. In dark mode the bright blue outline (`#2EC0FF`) ensures the theme toggle and other sidebar buttons are always discoverable, even when the button background is transparent.

#### `README.md`

Updated the VMware Clarity theme bullet under Streamlit UI features to reflect the new default (light) and the outlined button behaviour.

---

## Change Set 6 — Regenerate button

**Date:** 2026-06-17
**Branch:** `main`

### What was changed

#### `ui/ui-app.py`

**`_generate_response(user_prompt, version, model, temperature)`** (new function)  
Extracted the streaming + token-stats logic that was previously inlined inside the chat input handler into a standalone function. Both the normal chat input path and the new retry path call this function, eliminating code duplication.

**Regenerate button**  
A `↺ Regenerate` button is rendered immediately after the last assistant message whenever it is the most recent item in `st.session_state.messages`. It is never shown for historical messages mid-conversation.

Clicking it:
1. Pops the last assistant message from `st.session_state.messages`.
2. Sets `st.session_state.pending_retry = True` and calls `st.rerun()`.
3. On the next render the `pending_retry` guard detects that the last message is now the user question, clears the flag, and calls `_generate_response()` with the **current** temperature from the sidebar slider — so adjusting the slider before clicking retry produces a differently-sampled answer.

---

## Change Set 5 — VMware Clarity CSS/colour theme

**Date:** 2026-06-17
**Branch:** `main`

### What was added

#### `ui/themes.py` (new file)

Centralises all visual constants and CSS generation, matching the approach used in `personalHRAssistant/ui/themes.py`.

- **`DARK` palette** — built on the Clarity Design System construction scale (hsl 198). Key values: `bg_app=#1B2B32` (construction[1000]), `bg_sidebar=#17252B` (construction[1100]), `accent=#2EC0FF` (blue[400]).
- **`LIGHT` palette** — Clarity light surface with `bg_app=#F1F7F8` (construction[50]) and `accent=#0079AD` (blue[700]).
- **`PALETTES`** dict — keyed by `"dark"` / `"light"` for easy lookup.
- **`build_css(v)`** — accepts a palette dict and returns a `<style>` block covering: Streamlit CSS variable overrides, Metropolis `@font-face` declarations, app shell, typography, sidebar, buttons, text inputs, select boxes, radio buttons, slider, status widget, alerts, chat (input + message bubbles + code blocks), expanders, divider, scrollbar, and responsive breakpoints.

#### `ui/static/fonts/` (new directory)

18 Metropolis `.woff2` font files (weight 100–900, normal + italic), copied from `personalHRAssistant/ui/static/fonts/`. Streamlit serves these via `app/static/fonts/` at runtime.

#### `ui/ui-app.py`

- Imports `PALETTES, build_css` from `themes`.
- Initialises `st.session_state.theme = "dark"` on first load.
- Calls `st.markdown(build_css(PALETTES[...]), unsafe_allow_html=True)` immediately after `set_page_config` so the palette applies before any content renders.
- Adds a **theme toggle button** at the bottom of the sidebar ("☀️ Light mode" / "🌙 Dark mode") that flips `session_state.theme` and calls `st.rerun()`.

#### `README.md`

Added **VMware Clarity theme** bullet to the Streamlit UI features list.

---

## Change Set 4 — Token usage display in Streamlit UI

**Date:** 2026-06-10  
**Commit:** `(see below)`  
**Branch:** `main`

### What was added

#### `ui/ui-app.py`

**`_chunk_stat(chunk, key)`** helper  
Safely reads an integer stat from an Ollama streaming chunk, handling both dict-style (older library) and attribute-style (0.6.x typed objects) access. Returns 0 on missing/None values.

**`_token_caption(tokens)`** helper  
Renders a compact `st.caption` line under an assistant message:  
`↑ 8,432 prompt  ·  ↓ 312 completion  ·  97 tok/s`  
Only includes segments where the value is non-zero.

**Per-response token stats**  
After the streaming loop, the final Ollama chunk (`done=True`) is captured as `last_chunk`. Three fields are extracted:
- `prompt_eval_count` → prompt tokens (system prompt + RAG context + conversation history)
- `eval_count` → completion tokens generated
- `eval_duration` → nanoseconds spent generating; used to compute `tok/s`

The stats dict is passed to `_token_caption()` for immediate display, then stored inside the message dict (`message["tokens"]`) so the caption re-renders correctly when the chat history is replayed on subsequent Streamlit reruns.

**Session token total in sidebar**  
`st.session_state.session_tokens` accumulates prompt and completion tokens across all turns. The sidebar shows a `**Session tokens**` block once at least one response has been generated:
```
↑ 12,450 prompt
↓ 890 completion
13,340 total
```
Resets to zero when the user clicks **Clear Chat** or switches VCF version.

---

## Change Set 3 — README rewrite

**Date:** 2026-06-10  
**Commit:** `(see below)`  
**Branch:** `main`

Full rewrite of `README.md` to reflect all code changes made in Change Sets 1 and 2.

Key updates:
- **Quick Start** section added at the top — four commands to go from zero to running.
- **Part 1 (models)**: removed the `llama3` / `nomic-embed-text` history; shows only the current recommended models (`mxbai-embed-large` + `qwen3.5:35b-a3b`).
- **Part 2 (setup)**: corrected folder name (`privateAI-demo`, not `rag`); replaced individual `uv add` commands with `uv sync`.
- **Part 3 (ingestion)**: added multi-version ingestion table, `testSearch.py` usage, and note that re-runs are idempotent.
- **Part 4 (MCP server)**: documented `version` parameter and the two-call pattern for cross-version comparison queries.
- **Part 5 (Claude Desktop)**: replaced hardcoded `/Users/giuliano/` with `/Users/YOUR_USERNAME/`; corrected `--directory` to point to `privateAI-demo/` (project root, where `pyproject.toml` lives).
- **Part 7 (Streamlit UI)**: added `uv run streamlit run ui/ui-app.py` command; documented version selector, dynamic model list, clear chat, and conversation memory features.
- **Configuration table** (new section): documents all environment variables from `config.py` — `EMBED_MODEL`, `LLM_MODEL`, `OLLAMA_URL`, `DEFAULT_VERSION`, `NUM_CTX`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `BATCH_LIMIT`, `DEFAULT_N`, `VCF_OPS_URL`, `VCF_OPS_TOKEN`.
- **BGE-M3 switch**: updated from "edit model_name in the code" to `EMBED_MODEL=bge-m3 uv run rag/ingestData.py`; updated collection deletion command to use `uv run python -c` (no bare `python` / no hardcoded paths).
- **Multi-version section**: added instructions for adding VCF 9.2 (or any future version) — one line in `VERSION_MAP`, then re-ingest.

---

## Change Set 2 — Versioned Collections (VCF 9.0 / 9.1)

**Date:** 2026-06-10  
**Commit:** `(see below)`  
**Branch:** `main`

### Context

VCF 9.1 was released. Ingesting it into the existing single `docs` collection
would produce conflicting search results: the same topic described differently
across versions could appear in the same retrieval window, confusing the LLM.

**Decision:** Option A — separate ChromaDB collection per version.  
Each query hits exactly one version's data, guaranteeing zero cross-version conflicts.
Comparison questions ("what changed in 9.1?") work by calling the search tool
twice — once per version — which the LLM orchestrates automatically via MCP tool-calling.

### Migration steps (Option A)

1. Place `vmware-cloud-foundation-9.0.pdf` in `rag/contentData/` and run `uv run ingestData.py`
   → creates `docs_vcf90` collection.
2. Place `vmware-cloud-foundation-9-1.pdf` in `rag/contentData/` and run again
   → creates `docs_vcf91` collection.
3. Delete the legacy `docs` collection once verified:
   ```bash
   uv run python -c "import chromadb; chromadb.PersistentClient('rag/chroma_db').delete_collection('docs')"
   ```

### Files changed

#### `config.py`
- Removed `COLLECTION = "docs"` (single hardcoded name).
- Added `VERSION_MAP: dict[str, str]` — maps `"9.0"` → `"docs_vcf90"`, `"9.1"` → `"docs_vcf91"`.
- Added `DEFAULT_VERSION = "9.1"` (overridable via env var).
- Adding a new VCF version in future only requires adding one entry to `VERSION_MAP`.

#### `rag/ingestData.py`
- Added `version_from_filename()`: extracts `"9.0"` / `"9.1"` from a filename using
  a regex anchored to known product keywords (`foundation`, `vcf`, `cloud`), with a
  generic major.minor fallback.
- Files are grouped by detected version; each group is upserted into its own collection
  (`docs_vcf90`, `docs_vcf91`) via `config.VERSION_MAP`.
- Each chunk's metadata now includes `"version"` alongside `"source"` and `"page"`.
- Files whose version cannot be detected, or whose version is not in `VERSION_MAP`,
  are skipped with a clear hint message.
- Startup migration guard: warns if the legacy `docs` collection still exists.

#### `mcp/server.py`
- Added `_get_collection(version)` helper that opens the correct ChromaDB collection
  and raises a clear error (with fix instructions) if it does not exist.
- `search_vcf_documentation` now has a `version: str = config.DEFAULT_VERSION` parameter.
- Tool docstring explicitly instructs the LLM to call the tool twice for comparison questions.
- Result header updated to `[VCF {ver} | {source} | Page {page}]`.

#### `ui/ui-app.py`
- Replaced `init_db()` with two functions: `_init_chroma()` (shared client) and
  `get_collection(version)` (cached per version string).
- Added a version radio selector to the sidebar (sorted descending, defaults to latest).
- Auto-clears chat history when the user switches version, preventing answers from
  one version being mixed with questions about another.
- Chat input placeholder and system prompt are now version-aware.

#### `rag/testSearch.py`
- Added `--version` CLI argument (default: `config.DEFAULT_VERSION`).
- Help text lists all available versions from `config.VERSION_MAP` dynamically.

---

## Change Set 1 — Refactor & Critical Fixes

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
