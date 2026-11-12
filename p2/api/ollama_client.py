# from __future__ import annotations
import json
import os
from collections.abc import Iterator
from typing import Any
import requests

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
TIMEOUT = (5, float(os.getenv("OLLAMA_READ_TIMEOUT", "300")))


class OllamaError(RuntimeError):
    """
    Ollama unreachable, timed out, answered with an error, or sent an unexpeced payload.
    """

def _body(model: str, messages: list[dict], stream: bool,
            fmt: str | dict | None, options: dict | None) -> dict[str, Any]:
    body: dict[str, Any] = {"model": model, "messages": messages, "stream": stream}
    if fmt is not None:
        body["format"] = fmt
    if options:
        body["options"] = options
    return body

def chat(model: str, messages: list[dict], *, fmt: str | dict | None = None,
            options: dict | None = None) -> str:
    """
    Non-streaming call: returns the fill assistant messwage as a string.
    """
    try:
        r = requests.post(f"{OLLAMA_HOST}/api/chat",
                            json=_body(model, messages, False, fmt, options),
                            timeout=TIMEOUT)
    except requests.exceptions.RequestException as e:
        raise OllamaError(f"cannot get an answer from Ollama: {e}") from e
    if r.status_code != 200:
        raise OllamaError(f"{r.status_code}: {r.text}")
    try:
        return r.json()["message"]["content"]
    except (ValueError, KeyError, TypeError) as e:
        raise OllamaError(f"unexpected response from Ollama: {r.text[:200]}") from e

def chat_stream(model: str, messages: list[dict], *, fmt: str | dict | None = None,
                options: dict | None = None) -> Iterator[str]:
    """
    Streaming call: yields text fragmens. Ollama streams NDJSON, one JSON Objet per line.
    """
    try:
        with requests.post(f"{OLLAMA_HOST}/api/chat",
                            json=_body(model, messages, True, fmt, options),
                            stream=True, timeout=TIMEOUT) as r:
            if r.status_code != 200:
                raise OllamaError(f"{r.status_code}: {r.text}")
            for line in r.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                if "error" in chunk:
                    raise OllamaError(chunk["error"])
                yield chunk.get("message", {}).get("content", "")
                if chunk.get("done"):
                    break
    except requests.exceptions.RequestException as e:
        raise OllamaError(f"strem interrupted: {e}") from e
    except ValueError as e:
        raise OllamaError(f"invalid line in Ollama stream: {e}") from e
