"""
Seed the ChromaDB collection from a real directory, using ast.

Usage (from p2/api, venv active, CHROMA_PATH exported):
    python seed_ast.py ../../notes_app

Chunks follow contrat_schema_chromadb.md:
  id       = "{path}:{start_line}"
  document = raw source of the block (decorators included)
  metadata = path, name, kind, start_line, end_line, content_hash
"""
import ast
import hashlib
import os
import sys
from pathlib import Path

from retrieval import CHROMA_PATH, get_collection

SKIP_DIRS = {"node_modules", "dist", "build", "venv", "__pycache__"}


def iter_py_files(target: Path):
    for dirpath, dirnames, filenames in os.walk(target):
        dirnames[:] = sorted(d for d in dirnames
                             if d not in SKIP_DIRS and not d.startswith("."))
        for name in sorted(filenames):
            if name.endswith(".py"):
                yield Path(dirpath) / name


def make_chunk(rel: str, name: str, kind: str, start: int, end: int,
               lines: list[str]) -> dict:
    doc = "\n".join(lines[start - 1:end])
    return {
        "id": f"{rel}:{start}",
        "document": doc,
        "metadata": {
            "path": rel,
            "name": name,
            "kind": kind,
            "start_line": start,
            "end_line": end,
            "content_hash": hashlib.sha256(doc.encode("utf-8")).hexdigest(),
        },
    }


def chunk_file(path: Path, rel: str) -> list[dict]:
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    if not any(line.strip() for line in lines):
        return []

    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Fallback: the whole file becomes a single "module" chunk
        return [make_chunk(rel, Path(rel).name, "module", 1, len(lines), lines)]

    chunks = []
    first_start = None
    for node in ast.walk(tree):  # also finds methods nested in classes
        if isinstance(node, ast.ClassDef):
            kind = "class"
        elif isinstance(node, ast.AsyncFunctionDef):
            kind = "async_function"
        elif isinstance(node, ast.FunctionDef):
            kind = "function"
        else:
            continue
        # a decorator is above the "def" line: the block starts there
        start = min([node.lineno] + [d.lineno for d in node.decorator_list])
        chunks.append(make_chunk(rel, node.name, kind, start,
                                 node.end_lineno, lines))
        first_start = start if first_start is None else min(first_start, start)

    # "module" chunk: everything before the first symbol (docstring, imports)
    # or the whole file if it has no function or class
    header_end = (first_start - 1) if first_start else len(lines)
    while header_end > 0 and not lines[header_end - 1].strip():
        header_end -= 1
    if header_end > 0:
        chunks.append(make_chunk(rel, Path(rel).name, "module", 1,
                                 header_end, lines))

    chunks.sort(key=lambda c: c["metadata"]["start_line"])
    return chunks


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python seed_ast.py <target_dir>")
    target = Path(sys.argv[1]).resolve()
    if not target.is_dir():
        sys.exit(f"not a directory: {target}")

    # paths are relative to the PARENT of the target, so they look like
    # "notes_app/service.py" (same as the ids already in the base)
    base = target.parent
    col = get_collection()
    print(f"chroma path: {CHROMA_PATH}")

    for path in iter_py_files(target):
        rel = path.relative_to(base).as_posix()
        chunks = chunk_file(path, rel)
        # remove the old chunks of this file (stale ids, typos, shifted lines)
        col.delete(where={"path": rel})
        if chunks:
            col.upsert(ids=[c["id"] for c in chunks],
                       documents=[c["document"] for c in chunks],
                       metadatas=[c["metadata"] for c in chunks])
        print(f"{rel}: {len(chunks)} chunks")

    print("count:", col.count())


if __name__ == "__main__":
    main()