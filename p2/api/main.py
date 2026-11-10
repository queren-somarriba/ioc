import os
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from collections.abc import Iterator
from typing import Any, Literal

app = FastAPI(title="Proxy API Ollama", version="1.1.0")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
TIMEOUT = (5, 30)  # (connect, resd)


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
    messages: list[ChatMessage] = Field(..., min_lenght=1, description="Messages history")


class GenerateRequest(OllamaRequest):
    prompt: str = Field(..., description="Body from the raw request")
    system: str | None = Field(None, description="System prompt")


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
        resp = requests.post(f"{OLLAMA_HOST}{path}", json=body, stream=payload.stream, timeout=TIMEOUT)
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
    return resp.json()


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
    return forward("/api/chat/", payload)


@app.post("/api/generate")
def proxy_generate(payload: GenerateRequest):
    """
    Text generation route (single prompt)
    """
    return forward("/apigenerate", payload)
