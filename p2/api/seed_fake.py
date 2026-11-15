import os
import hashlib
import chromadb
from chromadb.utils import embedding_functions

client = chromadb.PersistentClient(
    path=os.getenv("CHROMA_PATH", "./data/chroma"))
ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2")
col = client.get_or_create_collection(
    "code_chunks", embedding_function=ef,
    metadata={"hnsw:space": "cosine"})

chunks = [
    ("notes_app/service.py", "search", "function", 29, 36,
     'ef search(self, term: str) -> list[Note]:\n             term = (term or "").strip().lower()\n             if not term:\n                 return []\n             return [n for n in self.storage.list_all()\n                 if term in n.title.lower() or term in n.body.lower()]'),
    ("notes_app/service.py", "create", "function", 17, 21,
     'def create(self, title: str, body: str = "", tags: list[str] | None = None) -> Note:\n        title = (title or "").strip()\n        if not title:\n            raise ValueError("title must not be empty")\n        return self.storage.add(title=title, body=body, tags=tags)')]

col.upsert(
    ids=[f"{p}:{s}" for p, _, _, s, _, _ in chunks],
    documents=[c[5] for c in chunks],
    metadatas=[{"path": p, "name": n, "kind": k,
                "start_line": s, "end_line": e}
               for p, n, k, s, e, _ in chunks])
print("count:", col.count())
