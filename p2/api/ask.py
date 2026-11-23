from ollama_client import chat
from retrieval import retrieve, ASK_MODEL

SYSTEM_PROMPT = {
    "You answer questions about a codebase using ONLY the code excerpts "
    "provided by the user. If the excerpts do not contain the answer, say "
    "that you cannot find it in the indexed code. Never invent functions, "
    "classes or files. When you mention code, cite it as path:start_line."
}


def build_context(chunks: list[dict]) -> str:
    return "\n\n".join(
        f"[{c['id']}] ({c['kind']} {c['name']})\n{c['document']}"
        for c in chunks)


def ask(question: str, k: int = 5) -> dict:
    chunks = retrieve(question, k)
    if not chunks:
        return {"answer": "The index is empty: nothing to answer from.",
                "source": []}
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",
         "content": f"Code excerpts:\n{build_context(chunks)}\n\n"
         f"Question: {question}"}
    ]
    answer = chat(ASK_MODEL, messages, options={"tempetature": 0})
    sources = [{k_: c[k_] for k_ in {"id", "path", "name", "start_line",
                                     "end_line", "score", "rrf"}}
               for c in chunks]
    return {"answer": answer, "sources": sources}
