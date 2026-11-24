import os
from typing import Any
import httpx


class ApiClientError(Exception):
    """Error from Fastapi or network layer"""
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ArchitectApiClient:
    def __init__(self, base_url: str | None = None) -> None:
        url = base_url or os.getenv("IOC_API_URL", "http://localhost:8000")
        self.base_url = url.rstrip("/")
        self._fast_client = httpx.AsyncClient(base_url=self.base_url, timeout=5.0)
        self._llm_client = httpx.AsyncClient(base_url=self.base_url, timeout=300.0)

    async def close(self) -> None:
        await self._fast_client.aclose()
        await self._llm_client.aclose()

    async def _request(
            self,
            client: httpx.AsyncCLient,
            method: str,
            path: str,
            *,
            params: dict[str, Any] | None = None,
            json: dict[str, Any] | None = None) -> Any:
        try:
            response = await client.request(method, path, params=params, json=json)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            detail = e.response.text.strip() or e.response.reason_phrase
            raise ApiClientError(
                f"Error HTTP {e.response.status_code} on {path} : {detail}",
                status_code=e.response.status_code) from e
        except httpx.HTTPError as e:
            raise ApiClientError(f"Impossible to reach the API ({path}) : {e}") from e

    async def get_status(self) -> dict[str, Any]:
        return await self._request(self._fast_client, "GET", "/status")

    async def get_files(self) -> list[dict[str, Any]]:
        data = await self._request(self._fast_client, "GET", "/files")
        return data if isinstance(data, list) else data.get("files", [])

    async def get_file(self, path: str) -> dict[str, Any]:
        return await self._request(self._fast_client, "GET", "/file", params={"path": path})

    async def get_chunks(self, page: int = 1, limit: int = 20) -> dict[str, Any]:
        return await self._request(
            self._fast_client, "GET", "/chunks", params={"page": page, "limit": limit}
        )

    async def post_context(self, question: str, k: int = 5) -> dict[str, Any]:
        return await self._request(
            self._llm_client, "POST", "/context", json={"question": question, "k": k}
        )

    async def post_ask(self, question: str, k: int = 5) -> dict[str, Any]:
        return await self._request(
            self._llm_client, "POST", "/ask", json={"question": question, "k": k}
        )
