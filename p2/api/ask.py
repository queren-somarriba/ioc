import re
from ollama_client import chat
from retrieval import (retrieve, ASK_MODEL, file_symbols,
                       find_symbols, list_files)

SYSTEM_PROMPT = (
    "You answer questions about a codebase using ONLY the code excerpts "
    "provided by the user. If the excerpts do not contain the answer, say "
    "that you cannot find it in the indexed code. Never invent functions, "
    "classes or files. When you mention code, cite the id of the excerpt "
    "in square brackets, for example [notes_app/service.py:17]."
    )


# ==========================================
# QUESTION DETECTION
# ==========================================

STOP_NAMES = {"it", "there", "this", "that", "anything", "something"}

EXISTS_PATTERNS = [
    re.compile(r"\b(?:function|method|class)\s+(?:called|named)\s+"
               r"[`'\"]?([A-Za-z_]\w*)", re.I),
    re.compile(r"\b(?:does|is)\s+[`'\"]?([A-Za-z_]\w*)[`'\"]?\s+"
               r"(?:exist|defined)\b", re.I),
]

LIST_PATTERN = re.compile(
    r"\b(?:functions|methods|classes|symbols)\b.*?"
    r"\b(?:in|of|from|inside)\s+[`'\"]?([\w./-]+\.\w+)", re.I)


# ==========================================
# ANSWERS BUILT FROM THE INDEX
# ==========================================

def _source_of(m: dict) -> dict:
    return {"id": f"{m['path']}:{m['start_line']}", "path": m["path"],
            "name": m['name'], "start_line": m['start_line'],
            "end_line": m["end_line"]}


def _result(answer: str, metas: list[dict]) -> dict:
    return {"answer": answer,
            "sources": [_source_of(m) for m in metas],
            "mode": "index"}


def resolve_path(given: str) -> list[str]:
    paths = [f["path"] for f in list_files()]
    if given in paths:
        return [given]
    return [p for p in paths if p.endswith("/" + given)]


def describe_symbols(metas: list[dict]) -> str:
    classes = [m for m in metas if m["kind"] == "class"]
    lines = []
    for m in metas:
        label = m["kind"]
        inside_class = any(c["start_line"] < m["start_line"]
                           and m["end_line"] <= c["end_line"]
                           for c in classes)
        if label != "class" and inside_class:
            label = "method"
        lines.append(f"- {label} `{m['name']}` "
                     f"(lines {m['start_line']}-{m['end_line']})")
    return "\n".join(lines)


def answer_exists(name: str) -> dict:
    metas = find_symbols(name)
    if not metas:
        return _result(f"No function, method or class named `{name}` "
                       "exists in the indexed code.", [])
    where = "\n".join(
        f"- `{m['name']}` ({m['kind']}) in {m['path']}, "
        f"lines {m['start_line']}-{m['end_line']}" for m in metas)
    return _result(f"Yes. `{name}` is defined here:\n{where}", metas)


def answer_list(given: str) -> dict:
    paths = resolve_path(given)
    if not paths:
        indexed = ", ".join(f["path"] for f in list_files()) or "(none)"
        return _result(f"`{given}` is not an indexed file. "
                       f"Indexed files: {indexed}.", [])
    if len(paths) > 1:
        return _result(f"`{given}` matches several indexed files: "
                       f"{', '.join(paths)}. Please give the full path.", [])
    metas = file_symbols(paths[0])
    if not metas:
        return _result(f"{paths[0]} is indexed but defines no function "
                       "or class.", [])
    return _result(f"{paths[0]} defines {len(metas)} symbols:\n"
                   f"{describe_symbols(metas)}", metas)


def answer_from_index(question: str) -> dict | None:
    m = LIST_PATTERN.search(question)
    if m:
        return answer_list(m.group(1))
    for pattern in EXISTS_PATTERNS:
        m = pattern.search(question)
        if m and m.group(1).lower() not in STOP_NAMES:
            return answer_exists(m.group(1))
    return None


# ==========================================
# RAG (fallback)
# ==========================================

def build_context(chunks: list[dict]) -> str:
    return "\n\n".join(
        f"[{c['id']}] ({c['kind']} {c['name']})\n{c['document']}"
        for c in chunks)


def ask(question: str, k: int = 5) -> dict:
    direct = answer_from_index(question)
    if direct is not None:
        return direct

    chunks = retrieve(question, k)
    if not chunks:
        return {"answer": "The index is empty: nothing to answer from.",
                "sources": [], "mode": "rag"}
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",
         "content": f"Code excerpts:\n{build_context(chunks)}\n\n"
         f"Question: {question}"}
    ]
    answer = chat(ASK_MODEL, messages, options={"temperature": 0})
    keys = ("id", "path", "name", "start_line", "end_line", "score", "rrf")
    return {"answer": answer,
            "sources": [{key: c[key] for key in keys} for c in chunks],
            "mode": "rag"}
