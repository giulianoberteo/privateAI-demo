"""
v1.2

Ingests PDF and TXT documents from ./contentData/ into versioned ChromaDB collections.

Changes from v1.1:
- Version-aware ingestion: each file is routed to its own collection based on the
  VCF version number detected from the filename (e.g. 9.0 → docs_vcf90, 9.1 → docs_vcf91).
  This guarantees zero cross-version contamination in search results.
- 'version' field added to every chunk's metadata for downstream filtering.
- Collection name driven by config.VERSION_MAP — no hardcoded strings.
- If a filename's version is not in VERSION_MAP, the file is skipped with a clear hint.
- Detects the legacy 'docs' collection and reminds the user to delete it after migration.

Migration from v1.x (single 'docs' collection):
  1. Place vmware-cloud-foundation-9.0.pdf in contentData/ and run this script
     → creates docs_vcf90 collection.
  2. Place vmware-cloud-foundation-9-1.pdf in contentData/ and run this script
     → creates docs_vcf91 collection.
  3. Delete the old collection once verified:
       python -c "import chromadb; chromadb.PersistentClient('./chroma_db').delete_collection('docs')"

Prerequisites:
- Ollama running locally with EMBED_MODEL pulled.
- PyMuPDF, chromadb, langchain-text-splitters, tqdm installed.
"""

import sys
import re
import pymupdf  # pyright: ignore[reportMissingImports]
import chromadb  # pyright: ignore[reportMissingImports]
from pathlib import Path
from chromadb.utils import embedding_functions  # pyright: ignore[reportMissingImports]
from langchain_text_splitters import RecursiveCharacterTextSplitter  # pyright: ignore[reportMissingImports]
from tqdm import tqdm  # pyright: ignore[reportMissingModuleSource]

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # pyright: ignore[reportMissingImports]


def version_from_filename(filename: str) -> str | None:
    """Extract VCF version string (e.g. '9.1') from a filename.

    Handles patterns like:
      vmware-cloud-foundation-9.0.pdf  →  '9.0'
      vmware-cloud-foundation-9-1.pdf  →  '9.1'
      vcf_9_0_docs.pdf                 →  '9.0'
    """
    # Prefer match anchored to a known product keyword for precision
    m = re.search(r'(?:foundation|vcf|cloud)[_\-.](\d+)[.\-_](\d+)', filename, re.IGNORECASE)
    if m:
        return f"{m.group(1)}.{m.group(2)}"
    # Generic fallback: first major.minor pattern in the filename
    m = re.search(r'(\d+)[.\-](\d+)', filename)
    return f"{m.group(1)}.{m.group(2)}" if m else None


# --- DB & embedding setup ---
client = chromadb.PersistentClient(path=str(config.DB_PATH))
emb_fn = embedding_functions.OllamaEmbeddingFunction(
    model_name=config.EMBED_MODEL,
    url=f"{config.OLLAMA_URL}/api/embeddings",
)
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=config.CHUNK_SIZE,
    chunk_overlap=config.CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
)

# --- Migration guard: warn if the legacy 'docs' collection still exists ---
try:
    client.get_collection(name="docs")
    print(
        "⚠️  Legacy 'docs' collection still present. Once the new versioned collections\n"
        "   are verified, remove it with:\n"
        "   python -c \"import chromadb; chromadb.PersistentClient('./chroma_db')"
        ".delete_collection('docs')\"\n"
    )
except Exception:
    pass

# --- Discover files ---
data_dir  = Path(__file__).resolve().parent / "contentData"
all_files = list(data_dir.glob("*.pdf")) + list(data_dir.glob("*.txt"))

if not all_files:
    print("❌ No PDF or TXT files found in contentData/")
    sys.exit(1)

print(f"📂 Found {len(all_files)} file(s) to process.")

# --- Group by detected version ---
files_by_version: dict[str, list[Path]] = {}
skipped: list[str] = []

for f in all_files:
    version = version_from_filename(f.name)
    if version is None:
        print(f"⚠️  Cannot detect version in '{f.name}' — skipping.")
        skipped.append(f.name)
        continue
    if version not in config.VERSION_MAP:
        print(f"⚠️  Version '{version}' (from '{f.name}') is not in config.VERSION_MAP — skipping.")
        print(f"   To add it: VERSION_MAP[\"{version}\"] = \"docs_vcf{version.replace('.', '')}\"")
        skipped.append(f.name)
        continue
    files_by_version.setdefault(version, []).append(f)

if not files_by_version:
    print("❌ No files matched a known version. Check config.VERSION_MAP.")
    sys.exit(1)


def flush_batch(col, docs, metas, ids):
    if not docs:
        return [], [], []
    try:
        col.upsert(documents=docs, metadatas=metas, ids=ids)
    except Exception as e:
        print(f"\n❌ Upsert failed: {e}")
        print(f"   Is Ollama running with '{config.EMBED_MODEL}' pulled?")
        sys.exit(1)
    return [], [], []


# --- Ingest ---
total_chunks = 0

for version, files in sorted(files_by_version.items()):
    col_name   = config.VERSION_MAP[version]
    collection = client.get_or_create_collection(name=col_name, embedding_function=emb_fn)
    print(f"\n📦 VCF {version} → collection '{col_name}'")

    for file_path in files:
        batch_docs, batch_metas, batch_ids = [], [], []

        if file_path.suffix.lower() == ".pdf":
            doc   = pymupdf.open(file_path)
            pages = [(i, page.get_text()) for i, page in enumerate(doc)]
        else:
            raw   = file_path.read_text(encoding="utf-8", errors="replace")
            pages = [(0, raw)]

        for page_num, text in tqdm(pages, desc=f"  {file_path.name}"):
            if len(text.strip()) < 20:
                continue
            for chunk_idx, chunk in enumerate(text_splitter.split_text(text)):
                batch_docs.append(chunk)
                batch_metas.append({
                    "source":  file_path.name,
                    "page":    page_num + 1,
                    "version": version,
                })
                batch_ids.append(f"{file_path.stem}_p{page_num}_c{chunk_idx}")

                if len(batch_docs) >= config.BATCH_LIMIT:
                    batch_docs, batch_metas, batch_ids = flush_batch(
                        collection, batch_docs, batch_metas, batch_ids
                    )
                    total_chunks += config.BATCH_LIMIT

        remainder = len(batch_docs)
        flush_batch(collection, batch_docs, batch_metas, batch_ids)
        total_chunks += remainder

if skipped:
    print(f"\n⚠️  Skipped {len(skipped)} file(s): {', '.join(skipped)}")

print(f"\n✅ Done — {total_chunks} chunks across {len(files_by_version)} version(s): "
      f"{', '.join(f'VCF {v}' for v in sorted(files_by_version))}.")
