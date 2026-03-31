import streamlit as st
import ollama
import chromadb
from chromadb.utils import embedding_functions

# --- 1. SETUP & CONFIG ---
st.set_page_config(page_title="VCF 9 Architect", page_icon="🛡️")
st.title("VCF9-Assistant")

# Connect to local ChromaDB with the same path and embedding function used during ingestion
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "rag" / "chroma_db"

client = chromadb.PersistentClient(path=DB_PATH)
emb_fn = embedding_functions.OllamaEmbeddingFunction(
    model_name="bge-m3", # Use bge-m3 or mxbai-embed-large
    url="http://localhost:11434/api/embeddings"
)
collection = client.get_collection(name="vcf_docs", embedding_function=emb_fn)

# --- 2. THE RAG ENGINE ---
def get_vcf_context(query):
    # Prepare the query for BGE/Mxbai
    instructional_query = f"Represent this sentence for searching relevant passages: {query}"
    results = collection.query(query_texts=[instructional_query], n_results=10)
    
    context_text = ""
    for i in range(len(results['documents'][0])):
        text = results['documents'][0][i]
        page = results['metadatas'][0][i]['page']
        context_text += f"\n[Source: Page {page}]\n{text}\n"
    return context_text

# --- 3. CHAT UI ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User Input
if prompt := st.chat_input("Ask about VCF 9..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Logic Flow
    with st.chat_message("assistant"):
        with st.status("Reading VCF 9 Manuals..."):
            context = get_vcf_context(prompt)
        
        # Call Ollama locally
        response = ollama.chat(
            model='qwen3.5:35b-a3b',
            messages=[
                {'role': 'system', 'content': f"You are a VCF Expert. Answer using this context: {context}"},
                {'role': 'user', 'content': prompt}
            ],
            stream=True # Enabling streaming for that "ChatGPT feel"
        )
        
        # Stream the response to the UI
        full_response = ""
        placeholder = st.empty()
        for chunk in response:
            full_response += chunk['message']['content']
            placeholder.markdown(full_response + "▌")
        placeholder.markdown(full_response)
        
    st.session_state.messages.append({"role": "assistant", "content": full_response})