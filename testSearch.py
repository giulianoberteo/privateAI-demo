import chromadb
import argparse
from chromadb.utils import embedding_functions

# 1. Setup the DB Connection (pointing to your existing rag folder)
client = chromadb.PersistentClient(path="../rag/chroma_db")
emb_fn = embedding_functions.OllamaEmbeddingFunction(
    model_name="mxbai-embed-large",
    url="http://localhost:11434/api/embeddings",
)
collection = client.get_collection(name="docs", embedding_function=emb_fn)

def quick_search(query, n=5):
    # Mandatory prefix for mxbai accuracy
    query_with_prefix = f"Represent this sentence for searching relevant passages: {query}"
    
    print(f"\n🔍 Searching for: '{query}'...")
    results = collection.query(query_texts=[query_with_prefix], n_results=n)
    
    if not results['documents'][0]:
        print("❌ No matches found. Try a different term.")
        return

    for i in range(len(results['documents'][0])):
        content = results['documents'][0][i]
        meta = results['metadatas'][0][i]
        print(f"\n[{i+1}] SOURCE: {meta['source']} (Page {meta['page']})")
        print(f"TEXT: {content[:800]}...") 
        print("-" * 50)

# 2. Setup the Command Line Argument Parser
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search the VCF9 Encyclopedia")
    
    # This allows you to pass the question as a string
    parser.add_argument("question", type=str, help="The question you want to ask your VCF9 docs")
    
    # Optional: Allow you to change the number of results via CLI (default is 5)
    parser.add_argument("-n", "--results", type=int, default=5, help="Number of results to return")

    args = parser.parse_args()
    
    # Execute search with the input from the terminal
    quick_search(args.question, n=args.results)