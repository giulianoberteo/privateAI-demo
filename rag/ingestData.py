"""
v1.1

Ingests PDF and TXT documents from ./contentData/ into a ChromaDB vector store.

Changes from v1.0:
- Switched collection.add() → upsert() so re-running the script on the same
  files is idempotent (no duplicate-ID errors).
- Added TXT file support alongside PDF.
- Paths now derived from __file__ so the script can be run from any directory.
- Final batch flush wrapped in the same error handler as mid-loop flushes.
- Shared constants imported from config.py (model name, chunk sizes, etc.).

Key Features:
- Processes all PDFs and TXTs in ./contentData/ with tqdm progress bars.
- Splits pages into configurable-size chunks (default 800 chars / 100 overlap).
- Batches upserts (default 20 chunks) to stay within Ollama memory limits.

Prerequisites:
- Ollama running locally (ollama pull mxbai-embed-large, or set EMBED_MODEL env var).
- ChromaDB at ./chroma_db/; PyMuPDF, chromadb, and tqdm installed.
"""

import sys
import pymupdf  # pyright: ignore[reportMissingImports]
import chromadb  # pyright: ignore[reportMissingImports]
from pathlib import Path
from chromadb.utils import embedding_functions  # pyright: ignore[reportMissingImports]
from langchain_text_splitters import RecursiveCharacterTextSplitter  # pyright: ignore[reportMissingImports]
from tqdm import tqdm  # pyright: ignore[reportMissingModuleSource]

# Resolve config.py from the project root (one level above rag/)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # pyright: ignore[reportMissingImports]

# --- DB & embedding setup ---
DB_PATH = Path(__file__).resolve().parent / "chroma_db"
client = chromadb.PersistentClient(path=str(DB_PATH))
emb_fn = embedding_functions.OllamaEmbeddingFunction(
    model_name=config.EMBED_MODEL,
    url=f"{config.OLLAMA_URL}/api/embeddings",
)
collection = client.get_or_create_collection(name=config.COLLECTION, embedding_function=emb_fn)

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=config.CHUNK_SIZE,
    chunk_overlap=config.CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
)

data_dir = Path(__file__).resolve().parent / "contentData"
pdf_files = list(data_dir.glob("*.pdf"))
txt_files = list(data_dir.glob("*.txt"))
all_files = pdf_files + txt_files

if not all_files:
    print("❌ No PDF or TXT files found in contentData/")
    sys.exit(1)

print(f"📂 Found {len(pdf_files)} PDF(s) and {len(txt_files)} TXT(s) to ingest.")

total_chunks = 0


def flush_batch(docs, metas, ids):
    """Upsert a batch and return empty lists. Exits on Ollama error."""
    if not docs:
        return [], [], []
    try:
        collection.upsert(documents=docs, metadatas=metas, ids=ids)
    except Exception as e:
        print(f"\n❌ Error upserting batch: {e}")
        print(f"   Hint: is 'ollama pull {config.EMBED_MODEL}' done? Is Ollama running?")
        sys.exit(1)
    return [], [], []


for file_path in all_files:
    batch_docs, batch_metas, batch_ids = [], [], []

    if file_path.suffix.lower() == ".pdf":
        doc = pymupdf.open(file_path)
        pages = [(i, page.get_text()) for i, page in enumerate(doc)]
    else:  # .txt
        raw = file_path.read_text(encoding="utf-8", errors="replace")
        pages = [(0, raw)]  # single "page" for TXT files

    for page_num, text in tqdm(pages, desc=f"Reading {file_path.name}"):
        if len(text.strip()) < 20:
            continue
        for chunk_idx, chunk in enumerate(text_splitter.split_text(text)):
            batch_docs.append(chunk)
            batch_metas.append({"source": file_path.name, "page": page_num + 1})
            batch_ids.append(f"{file_path.stem}_p{page_num}_c{chunk_idx}")

            if len(batch_docs) >= config.BATCH_LIMIT:
                batch_docs, batch_metas, batch_ids = flush_batch(batch_docs, batch_metas, batch_ids)
                total_chunks += config.BATCH_LIMIT

    # Flush remaining chunks for this file
    remainder = len(batch_docs)
    flush_batch(batch_docs, batch_metas, batch_ids)
    total_chunks += remainder

print(f"\n✅ Ingestion complete — {total_chunks} chunks indexed using {config.EMBED_MODEL}.")
