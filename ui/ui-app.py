import sys
import streamlit as st
import ollama
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # pyright: ignore[reportMissingImports]
from themes import PALETTES, build_css  # pyright: ignore[reportMissingImports]

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="Falcon Architect / VCF Specialist", page_icon="🛡️", layout="wide")

# --- THEME ---
if "theme" not in st.session_state:
    st.session_state.theme = "dark"
_dark = st.session_state.theme == "dark"
st.markdown(build_css(PALETTES["dark" if _dark else "light"]), unsafe_allow_html=True)

st.title("🚀 Falcon Architect 🔥 VCF Specialist")


# --- 2. DATA CONNECTIONS ---
@st.cache_resource
def _init_chroma():
    """Single ChromaDB client + embedding function shared across all version collections."""
    client = chromadb.PersistentClient(path=str(config.DB_PATH))
    emb_fn = embedding_functions.OllamaEmbeddingFunction(
        model_name=config.EMBED_MODEL,
        url=f"{config.OLLAMA_URL}/api/embeddings",
    )
    return client, emb_fn


@st.cache_resource
def get_collection(version: str):
    """Open the ChromaDB collection for the given VCF version (cached per version)."""
    client, emb_fn = _init_chroma()
    col_name = config.VERSION_MAP[version]
    try:
        return client.get_collection(name=col_name, embedding_function=emb_fn)
    except Exception as e:
        st.error(
            f"**VCF {version} collection not found.**  \n"
            f"Run `uv run ingestData.py` with the VCF {version} PDF in `rag/contentData/`.\n\n"
            f"Details: `{e}`"
        )
        st.stop()


@st.cache_data(ttl=30)
def get_available_models():
    try:
        result = ollama.list()
        names  = [m.model for m in result.models if m.model]
        return names if names else [config.LLM_MODEL, "qwen2.5:32b"]
    except Exception:
        return [config.LLM_MODEL, "qwen2.5:32b"]


# --- 3. TOKEN HELPERS ---
def _chunk_stat(chunk, key: str) -> int:
    """Safely read an integer stat from an Ollama streaming chunk (dict or object)."""
    try:
        val = chunk[key] if isinstance(chunk, dict) else getattr(chunk, key, None)
        return int(val) if val else 0
    except Exception:
        return 0


def _token_caption(tokens: dict) -> None:
    """Render a compact token-usage line under an assistant message."""
    prompt     = tokens.get("prompt", 0)
    completion = tokens.get("completion", 0)
    tps        = tokens.get("tok_per_sec", 0)

    parts = []
    if prompt:
        parts.append(f"↑ {prompt:,} prompt")
    if completion:
        parts.append(f"↓ {completion:,} completion")
    if tps:
        parts.append(f"{tps:,} tok/s")

    if parts:
        st.caption("  ·  ".join(parts))


# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("Settings")

    available_versions = sorted(config.VERSION_MAP.keys(), reverse=True)
    selected_version   = st.radio(
        "VCF Version",
        available_versions,
        index=0,
        horizontal=True,
    )

    st.divider()

    available_models = get_available_models()
    default_idx      = (
        available_models.index(config.LLM_MODEL)
        if config.LLM_MODEL in available_models else 0
    )
    selected_model = st.selectbox("Brain (LLM)", available_models, index=default_idx)

    temp = st.slider("Temperature", 0.0, 1.0, 0.1)

    st.divider()

    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages       = []
        st.session_state.session_tokens = {"prompt": 0, "completion": 0}
        st.rerun()

    st.info(f"Querying VCF **{selected_version}** docs only. Nothing leaves your machine.")

    st.divider()
    _toggle_label = "☀️ Light mode" if _dark else "🌙 Dark mode"
    if st.button(_toggle_label, use_container_width=True):
        st.session_state.theme = "light" if _dark else "dark"
        st.rerun()

    # Session token usage (shown once at least one response has been generated)
    session_t = st.session_state.get("session_tokens", {"prompt": 0, "completion": 0})
    session_total = session_t["prompt"] + session_t["completion"]
    if session_total > 0:
        st.divider()
        st.caption(
            f"**Session tokens**  \n"
            f"↑ {session_t['prompt']:,} prompt  \n"
            f"↓ {session_t['completion']:,} completion  \n"
            f"**{session_total:,} total**"
        )


# --- 5. AUTO-CLEAR ON VERSION SWITCH ---
if st.session_state.get("active_version") != selected_version:
    st.session_state.messages       = []
    st.session_state.session_tokens = {"prompt": 0, "completion": 0}
    st.session_state.active_version = selected_version


# --- 6. SESSION STATE INIT ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_tokens" not in st.session_state:
    st.session_state.session_tokens = {"prompt": 0, "completion": 0}


# --- 7. RAG ENGINE ---
def get_vcf_context(query: str, version: str):
    collection          = get_collection(version)
    instructional_query = f"{config.QUERY_PREFIX}{query}"
    results             = collection.query(
        query_texts=[instructional_query],
        n_results=config.DEFAULT_N + 5,
    )

    context_parts, sources = [], []
    for text, meta in zip(results["documents"][0], results["metadatas"][0]):
        page      = meta.get("page", "?")
        file_name = meta.get("source", "Manual")
        ver       = meta.get("version", version)
        context_parts.append(f"[VCF {ver} | {file_name} | Page {page}]\n{text}")
        sources.append(f"VCF {ver} — {file_name} (Pg. {page})")

    return "\n---\n".join(context_parts), list(dict.fromkeys(sources))


# --- 8. CHAT UI ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        # Re-render token stats for assistant messages that have them
        if message["role"] == "assistant" and "tokens" in message:
            _token_caption(message["tokens"])

if prompt := st.chat_input(f"Ask about VCF {selected_version} deployment, networking, or storage..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status(f"Consulting VCF {selected_version} library...") as status:
            context, source_list = get_vcf_context(prompt, selected_version)
            st.write("**References found:**")
            for s in source_list:
                st.write(f"- {s}")
            status.update(label="Analysing data...", state="complete")

        system_prompt = (
            f"You are a Senior VCF {selected_version} Architect. "
            "Use the provided documentation snippets to answer. "
            "Quote specific hardware specs or CLI commands exactly as they appear. "
            "If the answer is not in the documentation, say so clearly. "
            f"\n\nCONTEXT FROM VCF {selected_version} MANUALS:\n{context}"
        )

        ollama_messages = [{"role": "system", "content": system_prompt}]
        ollama_messages.extend(st.session_state.messages)

        response = ollama.chat(
            model=selected_model,
            messages=ollama_messages,
            options={"temperature": temp, "num_ctx": config.NUM_CTX},
            stream=True,
        )

        # Stream response — capture last chunk for token stats
        full_response = ""
        last_chunk    = None
        placeholder   = st.empty()
        for chunk in response:
            token = chunk["message"]["content"]
            if token:
                full_response += token
                placeholder.markdown(full_response + "▌")
            last_chunk = chunk
        placeholder.markdown(full_response)

        # Extract token stats from the final done=True chunk
        prompt_tokens     = _chunk_stat(last_chunk, "prompt_eval_count")
        completion_tokens = _chunk_stat(last_chunk, "eval_count")
        eval_duration_ns  = _chunk_stat(last_chunk, "eval_duration")
        tok_per_sec = (
            round(completion_tokens / (eval_duration_ns / 1e9))
            if eval_duration_ns > 0 else 0
        )

        tokens = {
            "prompt":      prompt_tokens,
            "completion":  completion_tokens,
            "tok_per_sec": tok_per_sec,
        }
        _token_caption(tokens)

        # Accumulate into session total
        st.session_state.session_tokens["prompt"]     += prompt_tokens
        st.session_state.session_tokens["completion"] += completion_tokens

    st.session_state.messages.append({
        "role":    "assistant",
        "content": full_response,
        "tokens":  tokens,
    })
