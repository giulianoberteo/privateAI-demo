import pymupdf # pyright: ignore[reportMissingImports]
import chromadb # pyright: ignore[reportMissingImports]
import os
from pathlib import Path
from chromadb.utils import embedding_functions # pyright: ignore[reportMissingImports]
from langchain_text_splitters import RecursiveCharacterTextSplitter # pyright: ignore[reportMissingImports]
from tqdm import tqdm # pyright: ignore[reportMissingModuleSource]

# Configure the connection to Chroma DB and the model to use
client = chromadb.PersistentClient(path="./chroma_db")
emb_fn = embedding_functions.OllamaEmbeddingFunction(
    model_name="mxbai-embed-large",
    url="http://localhost:11434/api/embeddings",
)
# Define the collection name and embedding function for Chroma DB
collection = client.get_or_create_collection(name="docs", embedding_function=emb_fn)

# define how to split the document ingestion and chunk sizes for mxbai
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,  # Reduced from 1200
    chunk_overlap=100,
    separators=["\n\n", "\n", ". ", " ", ""]
)
# point to the directory where the documents are stored
data_dir = Path("contentData")
pdf_files = list(data_dir.glob("*.pdf"))

# check if there's content to process
if not pdf_files:
    print("❌ No PDFs found!")
    exit()

# ingestion loop with progress bars and error handling
for pdf_path in pdf_files:
    doc = pymupdf.open(pdf_path)
    batch_docs, batch_metadatas, batch_ids = [], [], []
    
    # Reduce batch size to avoid memory issues with large documents and Mxbai's embedding limits
    BATCH_LIMIT = 20 

    for i, page in enumerate(tqdm(doc, desc=f"Reading {pdf_path.stem}")):
        text = page.get_text()
        if len(text.strip()) < 20: continue
        
        chunks = text_splitter.split_text(text)
        for j, chunk in enumerate(chunks):
            batch_docs.append(chunk)
            batch_metadatas.append({"source": pdf_path.name, "page": i + 1})
            batch_ids.append(f"{pdf_path.stem}_p{i}_c{j}")
            
            if len(batch_docs) >= BATCH_LIMIT:
                try:
                    collection.add(documents=batch_docs, metadatas=batch_metadatas, ids=batch_ids)
                except Exception as e:
                    print(f"\n❌ Error adding batch: {e}")
                    print("Hint: Check if 'ollama pull mxbai-embed-large' was run.")
                    exit()
                batch_docs, batch_metadatas, batch_ids = [], [], []

    # Final sweep
    if batch_docs:
        collection.add(documents=batch_docs, metadatas=batch_metadatas, ids=batch_ids)

print("\n✅ SUCCESS: VMware Cloud Foundation 9 docs is now indexed with Mxbai!")
