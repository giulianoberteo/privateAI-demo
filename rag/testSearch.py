"""
v1.2

CLI utility to run ad-hoc vector searches against a specific VCF version collection.
No LLM reasoning — raw ChromaDB results only.

Usage:
    uv run testSearch.py "your question here"
    uv run testSearch.py "your question here" -n 10
    uv run testSearch.py "your question here" --version 9.0
"""

import sys
import argparse
import chromadb
from pathlib import Path
from chromadb.utils import embedding_functions

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # pyright: ignore[reportMissingImports]

DB_PATH = Path(__file__).resolve().parent / "chroma_db"

client = chromadb.PersistentClient(path=str(DB_PATH))
emb_fn = embedding_functions.OllamaEmbeddingFunction(
    model_name=config.EMBED_MODEL,
    url=f"{config.OLLAMA_URL}/api/embeddings",
)


def quick_search(query: str, version: str, n: int = 5) -> None:
    if version not in config.VERSION_MAP:
        available = ", ".join(sorted(config.VERSION_MAP))
        print(f"❌ Unknown version '{version}'. Available: {available}")
        return

    col_name = config.VERSION_MAP[version]
    try:
        collection = client.get_collection(name=col_name, embedding_function=emb_fn)
    except Exception:
        print(f"❌ Collection '{col_name}' not found. Run ingestData.py with the VCF {version} PDF first.")
        return

    query_with_prefix = f"{config.QUERY_PREFIX}{query}"
    print(f"\n🔍 VCF {version} | '{query}'  (top {n}, model: {config.EMBED_MODEL})\n")

    results = collection.query(query_texts=[query_with_prefix], n_results=n)

    if not results["documents"][0]:
        print("❌ No matches found. Try a different term.")
        return

    for i, (content, meta) in enumerate(
        zip(results["documents"][0], results["metadatas"][0]), start=1
    ):
        source = meta.get("source", "unknown")
        page   = meta.get("page", "?")
        print(f"[{i}] {source}  (Page {page})")
        print(f"    {content[:800].strip()}")
        print("-" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search a VCF version's vector index")
    parser.add_argument("question", type=str, help="Question or keyword to search")
    parser.add_argument("-n", "--results", type=int, default=5, help="Number of results (default: 5)")
    parser.add_argument(
        "--version", type=str, default=config.DEFAULT_VERSION,
        help=f"VCF version to search. Available: {', '.join(sorted(config.VERSION_MAP))}. "
             f"Default: {config.DEFAULT_VERSION}",
    )
    args = parser.parse_args()
    quick_search(args.question, version=args.version, n=args.results)
