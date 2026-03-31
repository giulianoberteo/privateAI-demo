import streamlit as st
import ollama
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path  # Fixed: Added missing import

# --- 1. SETUP & CONFIG ---
st.set_page_config(page_title="VCF 9 Architect", page_icon="🛡️", layout="wide")
st.title("🛡️ VCF9-Assistant")

# .parents[0] is ui/
# .parents[1] is privateAI-demo/
BASE_DIR = Path(__file__).resolve().parents[1] 
DB_PATH = BASE_DIR / "rag" / "chroma_db"

# --- SIDEBAR: CONTROL PANEL ---
with st.sidebar:
    st.header("Settings")
    # Model Selection
    selected_model = st.selectbox("Brain", ["qwen3.5:35b-a3b", "qwen2.5:32b"], index=0)
    # Creativity Control (Lower is better for technical docs)
    temp = st.slider("Temperature", 0.0, 1.0, 0.1)
    
    st.divider()
    st.info("This assistant uses local RAG to answer questions based on your private VCF 9 library.")

# --- 2. DATA CONNECTIONS ---
@st.cache_resource # Keeps the connection open so it doesn't reload every click
def init_db():
    client = chromadb.PersistentClient(path=str(DB_PATH))
    emb_fn = embedding_functions.OllamaEmbeddingFunction(
        model_name="bge-m3", 
        url="http://localhost:11434/api/embeddings"
    )
    # Ensure collection exists before getting
    return client.get_collection(name="docs", embedding_function=emb_fn)

collection = init_db()

# --- 3. THE RAG ENGINE ---
def get_vcf_context(query):
    instructional_query = f"Represent this sentence for searching relevant passages: {query}"
    results = collection.query(query_texts=[instructional_query], n_results=25)
    
    context_text = ""
    sources = []
    for i in range(len(results['documents'][0])):
        text = results['documents'][0][i]
        metadata = results['metadatas'][0][i]
        page = metadata.get('page', 'Unknown')
        file_name = metadata.get('source', 'Manual')
        
        context_text += f"\n---\n[Source: {file_name} | Page {page}]\n{text}\n"
        sources.append(f"{file_name} (Pg. {page})")
        
    return context_text, sources

# --- 4. CHAT UI ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User Input
if prompt := st.chat_input("Ask about VCF 9 deployment, networking, or storage..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # Step 1: Retrieval
        with st.status("Consulting VCF 9 Library...") as status:
            context, source_list = get_vcf_context(prompt)
            st.write("**References found:**")
            for s in set(source_list): # Unique list of sources
                st.write(f"- {s}")
            status.update(label="Analyzing Data...", state="complete")
        
        # Step 2: Generation with Qwen 3.5
        # Enhanced System Prompt for the new model
        system_prompt = (
            "You are a Senior VCF 9 Architect. Use the provided documentation snippets to answer. "
            "If the documentation mentions specific hardware specs or CLI commands, provide them exactly. "
            "If the answer isn't in the text, state that you don't have that specific data. "
            f"\n\nCONTEXT FROM VCF MANUALS:\n{context}"
        )

        response = ollama.chat(
            model=selected_model,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt}
            ],
            options={'temperature': temp}, # Connect to sidebar slider
            stream=True
        )
        
        # Step 3: Streaming Output
        full_response = ""
        placeholder = st.empty()
        for chunk in response:
            full_response += chunk['message']['content']
            placeholder.markdown(full_response + "▌")
        placeholder.markdown(full_response)
        
    st.session_state.messages.append({"role": "assistant", "content": full_response})