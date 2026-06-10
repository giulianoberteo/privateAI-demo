import sys
import streamlit as st
import ollama
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # pyright: ignore[reportMissingImports]

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="VCF Architect", page_icon="🛡️", layout="wide")
st.title("🛡️ VCF Assistant")


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


# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("Settings")

    # Version selector — sorted descending so latest is first
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
        st.session_state.messages = []
        st.rerun()

    st.info(f"Querying VCF **{selected_version}** docs only. Nothing leaves your machine.")


# --- 4. AUTO-CLEAR ON VERSION SWITCH ---
# Reset conversation when the user switches version to avoid context bleed
# between answers sourced from different collections.
if st.session_state.get("active_version") != selected_version:
    st.session_state.messages       = []
    st.session_state.active_version = selected_version


# --- 5. RAG ENGINE ---
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


# --- 6. CHAT UI ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

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

        full_response = ""
        placeholder   = st.empty()
        for chunk in response:
            token = chunk["message"]["content"]
            if token:
                full_response += token
                placeholder.markdown(full_response + "▌")
        placeholder.markdown(full_response)

    st.session_state.messages.append({"role": "assistant", "content": full_response})
