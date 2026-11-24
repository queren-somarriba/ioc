
from __future__ import annotations

from dataclasses import dataclass

from .config import Settings

import hashlib
from .chunker import chunk_file
from .store import ChunkStore
from .walker import FileFilter



@dataclass
class IndexEvent:
    
    type: str        
    path: str
    chunks: int = 0


class Indexer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.files = FileFilter(settings)
        self.store =ChunkStore(chroma_path=settings.chroma_path, model_cache=settings.model_cache, collection=settings.collection)

    def index_file(self, rel_path: str) -> IndexEvent:
        """Index a file, without changing the index if the file is unchanged."""
        text = self.files.read_text(rel_path)
        if text is None:
            return self.remove_file(rel_path)
        chunks = chunk_file(rel_path, text)
        ids = []
        documents = []
        metadatas = []
        for chunk in chunks:
            content_hash = hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()
            chunk_id = f"{chunk.path}:{chunk.start_line}"
            ids.append(chunk_id)
            documents.append(chunk.text)
            metadatas.append({
                "path": chunk.path,
                "name": chunk.name,
                "kind": chunk.kind,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "content_hash": content_hash,
            })
        existing = self.store.file_chunks(rel_path)
        new_ids = set(ids)
        stale_ids = set(existing.keys()) - new_ids
        self.store.delete_ids(list(stale_ids))
        to_write = []
        for i in range(len(ids)):
            old = existing.get(ids[i])
            if old is None or old["content_hash"] != metadatas[i]["content_hash"]:
                to_write.append(i)
        self.store.upsert([ids[i] for i in to_write], [documents[i] for i in to_write], [metadatas[i] for i in to_write])
        return IndexEvent(type="indexed", path=rel_path, chunks=len(chunks))
        
    def remove_file(self, rel_path: str) -> IndexEvent:
        self.store.delete_path(rel_path)
        return IndexEvent(type="deleted", path=rel_path)

    def sync(self) -> None:
        """Synchronize the index with the current state of the target directory."""
        on_disk = set(self.files.scan())
        in_db = self.store.indexed_path()
        for path in in_db - on_disk:
            self.remove_file(path)
        for path in on_disk:
            self.index_file(path)
