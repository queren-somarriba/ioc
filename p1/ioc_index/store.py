
from __future__ import annotations
import chromadb


from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction



class ChunkStore:
    def __init__(self, chroma_path: str, model_cache: str, collection: str = "code_chunks") -> None:
        client = chromadb.PersistentClient(path=str(chroma_path))
        ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2", cache_folder=str(model_cache))
        self.collection = client.get_or_create_collection(
            name=collection,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, ids: list[str], documents: list[str], metadatas: list[dict]) -> None:
        if not ids:
            return
        self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)


    def delete_ids(self, ids: list[str]) -> None:
        if not ids:
            return
        self.collection.delete(ids=ids)

    def delete_path(self, path: str) -> None:
        self.collection.delete(where={"path": path})

    def file_chunks(self, path: str) -> dict[str, dict]:
        """return the metadada of all chunks of a file, keyed by chunk_id"""
        result = self.collection.get(where={"path": path}, include=["metadatas"])
        chunks = {}
        for chunk_id, meta in zip(result["ids"], result["metadatas"]):
            chunks[chunk_id] = meta
        return chunks

    def count(self) -> int:
        return self.collection.count()
    
    def indexed_path(self) -> list[str]:
        """List of path that have chunks in the collection."""
        result = self.collection.get(include=["metadatas"])
        paths = set()
        for meta in result["metadatas"]:
            paths.add(meta["path"])
        return paths
