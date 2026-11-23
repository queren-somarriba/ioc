import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from collections.abc import Iterator
from typing import Any, Literal
from ollama_client import OLLAMA_HOST, TIMEOUT, OllamaError
from retrieval import retrieve, index_status, list_files, file_chunks, list_chunks
from ask import run_ask

app = FastAPI(title="Proxy API Ollama", version="1.1.0")


# ==========================================
# PYDANTIC MODEL
# ==========================================

class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class OllamaRequest(BaseModel):
    model: str = Field(..., min_length=1, description="Name of the model")
    stream: bool = Field(False, description="Activate/Deactivate the answer streaming")
    format: str | dict[str, Any] | None = Field(None, description='"json" or JSON schema')
    options: dict[str, Any] | None = Field(None, description="temperature, num_ctx...")


class ChatRequest(OllamaRequest):
    messages: list[ChatMessage] = Field(..., min_length=1, description="Messages history")


class GenerateRequest(OllamaRequest):
    prompt: str = Field(..., description="Body from the raw request")
    system: str | None = Field(None, description="System prompt")


class ContextRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User intent or question")
    k: int = Field(5, ge=1, le=20, description="Number of chunks to retrieve")


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    k: int = Field(5, ge=1, le=10)


# ==========================================
# FORWARDING
# ==========================================

def iter_ndjson(resp: requests.Response) -> Iterator[bytes]:
    """
    Forward the stream line by line and always close
    """
    try:
        for line in resp.iter_lines():
            if line:
                yield line + b"\n"
    finally:
        resp.close()


def forward(path: str, payload: OllamaRequest):
    body = payload.model_dump(exclude_none=True)
    try:
        resp = requests.post(f"{OLLAMA_HOST}{path}", json=body,
                             stream=payload.stream, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError as e:
        raise HTTPException(status_code=503, detail="Cannot reach Ollame service.") from e
    except requests.exceptions.Timeout as e:
        raise HTTPException(status_code=504, detail="Ollama time out.") from e
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text) from e
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if payload.stream:
        return StreamingResponse(iter_ndjson(resp), media_type="application/x-ndjson")
    try:
        return resp.json()
    except ValueError as e:
        raise HTTPException(status_code=502, detail="Ollama returned invalid JSON.") from e


@app.exception_handler(OllamaError)
def ollama_error_handler(request, exc: OllamaError):
    """
    Any OllamaError raised by the internal client(/ask, patch loop)
    becomes a clean 502.
    """
    return JSONResponse(status_code=502, content={"detail": str(exc)})


# ==========================================
# API ROUTES
# ==========================================

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat")
def proxy_chat(payload: ChatRequest):
    """
    Chat route validated with Pydantic, forwarded to the Ollama container
    """
    return forward("/api/chat", payload)


@app.post("/api/generate")
def proxy_generate(payload: GenerateRequest):
    """
    Text generation route (single prompt)
    """
    return forward("/api/generate", payload)


@app.post("/context")
def context(payload: ContextRequest):
    """
    Return the top-k most relevant chunks for a given intent.
    """
    chunks = retrieve(payload.query, payload.k)
    return {"query": payload.query, "k": payload.k, "chunks": chunks}


@app.get("/status")
def status():
    return index_status()


@app.get("/files")
def files():
    return list_files()


@app.get("/file")
def file(path: str = Query(..., min_length=1)):
    chunks = file_chunks(path)
    if not chunks:
        raise HTTPException(status_code=404, detail=f"No indexed file: {path}")
    return {"path": path, "chunks": chunks}


@app.get("/chunks")
def chunks(offset: int = Query(0, ge=0),
           limit: int = Query(20, ge=1, le=100)):
    return list_chunks(offset, limit)


@app.post("/ask")
def ask_route(payload: AskRequest):
    return run_ask(payload.question, payload.k)