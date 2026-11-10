import os
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Proxy API Ollama", version="1.0.0")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")


# ==========================================
# PYDANTIC MODEL
# ==========================================

class ChatMessage(BaseModel):
    role: str = Field(..., description="Author role (ex: user, assistant, system)")
    content: str = Field(..., description="Textual content of the message")


class ChatRequest(BaseModel):
    model: str = Field(..., description="Name of the model")
    messages: list[ChatMessage] = Field(..., description="Messages history")
    stream: bool = Field(False, description="Activate/Deactivate the answer streaming")


class GenerateRequest(BaseModel):
    model: str = Field(..., dscription="Name of the model")
    prompt: str = Field(..., description="Body from the raw request")
    stream: bool = Field(False, description="Activate/Deactivate the answer streaming")


# ==========================================
# API ROUTES
# ==========================================

@app.post("/api/chat")
def proxy_chat(payload: ChatRequest):
    """
    Chat route validate with Pydantic, send the request to Ollama container
    """
    url = f"{OLLAMA_HOST}/api/chat"
    try:
        response = requests.post(url, json=payload.model_dump(), stream=payload.stream, timeout=120)
        response.raise_for_status()
        if payload.stream:
            return StreamingResponse(
                response.iter_content(chunk_size=1024), media_type="application/x-ndjson"
            )
        return response.json()
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="Cannot reach Ollama service.")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate")
def proxy_generate(payload: GenerateRequest):
    """
    Generation text route (for unique prompt)
    """
    url = f"{OLLAMA_HOST}/api/generate"
    try:
        response = requests.post(url, json=payload.model_dump(), stream=payload.stream, timeout=120)
        response.raise_for_status()
        if payload.stream:
            return StreamingResponse(
                response.iter_content(chunk_size=1024), media_type="application/x-ndjson"
            )
        return response.json()
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="Cannot reach Ollama service.")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))
