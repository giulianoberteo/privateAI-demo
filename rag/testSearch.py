"""
v1.1

CLI utility to run ad-hoc ChromaDB queries against the indexed VCF documentation.
No LLM reasoning — raw vector search results only.

Usage:
    uv run testSearch.py "your question here"
    uv run testSearch.py "your question here" -n 10
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
collection = client.get_collection(name=config.COLLECTION, embedding_function=emb_fn)


def quick_search(query: str, n: int = 5) -> None:
    query_with_prefix = f"{config.QUERY_PREFIX}{query}"
    print(f"\n🔍 Searching for: '{query}'  (top {n} results, model: {config.EMBED_MODEL})\n")

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
    parser = argparse.ArgumentParser(description="Search the VCF 9 vector index")
    parser.add_argument("question", type=str, help="Question or keyword to search")
    parser.add_argument("-n", "--results", type=int, default=5, help="Number of results (default: 5)")
    args = parser.parse_args()
    quick_search(args.question, n=args.results)
