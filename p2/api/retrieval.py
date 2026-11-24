import os
import chromadb
from chromadb.utils import embedding_functions
import re
from rank_bm25 import BM25Okapi
from ollama_client import OLLAMA_HOST

CHROMA_PATH = os.getenv("CHROMA_PATH", "./data/chroma")
COLLECTION_NAME = "code_chunks"

ASK_MODEL = os.getenv("ASK_MODEL", "qwen2.5:3b")
CODE_MODEL = os.getenv("CODE_MODEL", "qwen2.5-coder:3b")
TARGET_PATH = os.getenv("TARGET_PATH", "./notes_app/")

_collection = None
RRF_K = 60


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


def tokenize(text: str) -> list[str]:
    out = []
    for tk in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text):
        out.append(tk.lower())
        spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", tk).replace("_", " ")
        parts = spaced.lower().split()
        if len(parts) > 1:
            out.extend(parts)
    return out


def retrieve(query: str, k: int = 5) -> list[dict]:
    """
    Top-k chunks : vectorial similarity + BM25
    """
    col = get_collection()
    total = col.count()
    if total == 0:
        return []
    pool = min(total, max(20, k * 4))

    # vectorial ranking
    res = col.query(query_texts=[query], n_results=pool,
                    include=["documents", "metadatas", "distances"])
    info = {}
    vec_order = []
    for cid, doc, meta, dist in zip(res["ids"][0], res["documents"][0],
                                    res["metadatas"][0], res["distances"][0]):
        info[cid] = {"document": doc, "meta": meta,
                     "score": round(1 - dist, 4), "bm25": 0.0}
        vec_order.append(cid)

    # bm25 ranking
    allc = col.get(include=["documents", "metadatas"])
    bm25 = BM25Okapi([tokenize(d) for d in allc["documents"]])
    scores = bm25.get_scores(tokenize(query))
    ranked = sorted(range(len(allc["ids"])), key=lambda i: -scores[i])
    bm_order = []
    for i in ranked[:pool]:
        if scores[i] <= 0:
            break
        cid = allc["ids"][i]
        bm_order.append(cid)
        if cid not in info:
            info[cid] = {"document": allc["documents"][i],
                         "meta": allc["metadatas"][i],
                         "score": None, "bm25": 0.0}
        info[cid]["bm25"] = round(float(scores[i]), 4)

    # RRF fusion
    rrf = {}
    for order in (vec_order, bm_order):
        for rank, cid in enumerate(order):
            rrf[cid] = rrf.get(cid, 0.0) + 1.0 / (RRF_K + rank + 1)

    chunks = []
    for cid in sorted(rrf, key=lambda c: -rrf[c])[:k]:
        m = info[cid]["meta"]
        chunks.append({
            "id": cid,
            "path": m["path"], "name": m["name"], "kind": m["kind"],
            "start_line": m["start_line"], "end_line": m["end_line"],
            "document": info[cid]["document"],
            "score": info[cid]["score"],
            "bm25": info[cid]["bm25"],
            "rrf": round(rrf[cid], 5)
        })
    return chunks


def index_status() -> dict:
    return {
        "chunks": get_collection().count(),
        "target_path": TARGET_PATH,
        "chroma_path": CHROMA_PATH,
        "ask_model": ASK_MODEL,
        "code_model": CODE_MODEL,
        "ollama_host": OLLAMA_HOST
    }


def list_files() -> list[dict]:
    metas = get_collection().get(include=["metadatas"])["metadatas"]
    counts: dict[str, int] = {}
    for m in metas:
        counts[m["path"]] = counts.get(m["path"], 0) + 1
    return [{"path": p, "chunks": n} for p, n in sorted(counts.items())]


def file_chunks(path: str) -> list[dict]:
    r = get_collection().get(where={"path": path}, 
                             include=["documents", "metadatas"])
    out = [{"id": i, "document": d, **m}
           for i, d, m in zip(r["ids"], r["documents"], r["metadatas"])]
    return sorted(out, key=lambda c: c["start_line"])


def list_chunks(offset: int, limit: int) -> dict:
    col = get_collection()
    r = col.get(limit=limit, offset=offset, include=["documents", "metadatas"])
    items = [{"id": i, "document": d, **m}
             for i, d, m in zip(r["ids"], r["documents"], r["metadatas"])]
    return {"total": col.count(), "offset": offset,
            "limit": limit, "items": items}


def find_symbols(name: str,
                 kinds=("function", "async_function", "class")) -> list[dict]:
    r = get_collection().get(where={"name": name}, include=["metadatas"])
    return [m for m in r["metadatas"] if m["kind"] in kinds]


def file_symbols(path: str) -> list[dict]:
    r = get_collection().get(where={"path": path}, include=["metadatas"])
    metas = [m for m in r["metadatas"] if m["kind"] != "module"]
    return sorted(metas, key=lambda m: m["start_line"])
