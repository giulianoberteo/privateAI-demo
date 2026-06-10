import sys
import streamlit as st
import ollama
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # pyright: ignore[reportMissingImports]

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="VCF 9 Architect", page_icon="🛡️", layout="wide")
st.title("🛡️ VCF9-Assistant")


# --- 2. DATA CONNECTIONS ---
@st.cache_resource
def init_db():
    try:
        client = chromadb.PersistentClient(path=str(config.DB_PATH))
        emb_fn = embedding_functions.OllamaEmbeddingFunction(
            model_name=config.EMBED_MODEL,
            url=f"{config.OLLAMA_URL}/api/embeddings",
        )
        return client.get_collection(name=config.COLLECTION, embedding_function=emb_fn)
    except Exception as e:
        st.error(
            f"**ChromaDB not found.** Run `uv run ingestData.py` first to build the index.\n\n"
            f"Details: `{e}`"
        )
        st.stop()


@st.cache_data(ttl=30)
def get_available_models():
    """Fetch installed Ollama models; fall back to defaults if Ollama is unreachable."""
    try:
        result = ollama.list()
        names = [m.model for m in result.models if m.model]
        return names if names else [config.LLM_MODEL, "qwen2.5:32b"]
    except Exception:
        return [config.LLM_MODEL, "qwen2.5:32b"]


collection = init_db()

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("Settings")

    available_models = get_available_models()
    default_idx = available_models.index(config.LLM_MODEL) if config.LLM_MODEL in available_models else 0
    selected_model = st.selectbox("Brain (LLM)", available_models, index=default_idx)

    temp = st.slider("Temperature", 0.0, 1.0, 0.1)

    st.divider()

    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.info("Answers are grounded in your private VCF 9 library — nothing leaves your machine.")


# --- 4. RAG ENGINE ---
def get_vcf_context(query: str):
    instructional_query = f"{config.QUERY_PREFIX}{query}"
    results = collection.query(query_texts=[instructional_query], n_results=config.DEFAULT_N + 5)

    context_parts = []
    sources = []
    for text, meta in zip(results["documents"][0], results["metadatas"][0]):
        page      = meta.get("page", "?")
        file_name = meta.get("source", "Manual")
        context_parts.append(f"[Source: {file_name} | Page {page}]\n{text}")
        sources.append(f"{file_name} (Pg. {page})")

    return "\n---\n".join(context_parts), list(dict.fromkeys(sources))


# --- 5. CHAT UI ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask about VCF 9 deployment, networking, or storage..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # Step 1: Retrieval
        with st.status("Consulting VCF 9 Library...") as status:
            context, source_list = get_vcf_context(prompt)
            st.write("**References found:**")
            for s in source_list:
                st.write(f"- {s}")
            status.update(label="Analysing data...", state="complete")

        # Step 2: Build message list for Ollama
        # System prompt carries the fresh RAG context; history below preserves
        # conversation continuity across turns.
        system_prompt = (
            "You are a Senior VCF 9 Architect. Use the provided documentation snippets to answer. "
            "If the documentation mentions specific hardware specs or CLI commands, provide them exactly. "
            "If the answer isn't in the documentation, say so clearly. "
            f"\n\nCONTEXT FROM VCF MANUALS:\n{context}"
        )

        ollama_messages = [{"role": "system", "content": system_prompt}]
        # Append full conversation history (includes the just-added user message)
        ollama_messages.extend(st.session_state.messages)

        # Step 3: Stream response
        response = ollama.chat(
            model=selected_model,
            messages=ollama_messages,
            options={"temperature": temp, "num_ctx": config.NUM_CTX},
            stream=True,
        )

        full_response = ""
        placeholder = st.empty()
        for chunk in response:
            token = chunk["message"]["content"]
            if token:
                full_response += token
                placeholder.markdown(full_response + "▌")
        placeholder.markdown(full_response)

    st.session_state.messages.append({"role": "assistant", "content": full_response})
