import os
import chromadb
from chromadb.utils import embedding_functions

CHROMA_PATH = os.getenv("CHROMA_PATH", "./data/chroma")
COLLECTION_NAME = "code_chunks"

_collection = None


def get_collection():
    """
    Open Chroma client only once (singleton per process)
    """
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2")
        _collection = client.get_or_create_collection(
            COLLECTION_NAME,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"})
    return _collection


def retrieve(query: str, k: int = 5) -> list[dict]:
    """
    Top-k closest chunks from the request, with their score. 
    """
    col = get_collection()
    total = col.count()
    if total == 0:
        return []
    res = col.query(
        query_texts=[query],
        n_results=min(k, total),
        include=["documents", "metadatas", "distances"])

    chunks = []
    for doc, meta, dist in zip(res["documents"][0],
                               res["metadatas"][0],
                               res["distances"][0]):
        chunks.append({
            "id": f"{meta['path']}:{meta['start_line']}",
            "path": meta["path"],
            "name": meta["name"],
            "kind": meta["kind"],
            "start_line": meta["start_line"],
            "end_line": meta["end_line"],
            "document": doc,
            "score": round(1 - dist, 4)
        })
    return chunks
