"""HTTP request execution.

Port of ``pkg/request/executor.go``: builds the endpoint from path/query
parameters, issues the request and returns a ``{"status_code", "body"}`` JSON
document as the tool result text.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from .models import Request

DEFAULT_TIMEOUT = 30.0


class ExecutorError(RuntimeError):
    """Raised when a request cannot be built or the API responds with an error."""


class HttpExecutor:
    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout, follow_redirects=True
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    def _build_endpoint(self, request: Request, arg_values: dict[str, str]) -> str:
        endpoint = request.endpoint

        for param in request.path_params:
            if param not in arg_values:
                raise ExecutorError(f"missing required path param: {param}")
            endpoint = endpoint.replace(":" + param, quote(arg_values[param], safe=""))

        query: dict[str, str] = {}
        for key in request.query_params:
            if key in arg_values:
                query[key] = arg_values[key]

        if query:
            encoded = urlencode(sorted(query.items()))
            separator = "&" if "?" in endpoint else "?"
            endpoint += separator + encoded

        return endpoint

    async def execute(self, request: Request, arg_values: dict[str, str]) -> str:
        endpoint = self._build_endpoint(request, arg_values)
        scheme = "https" if request.secure else "http"
        url = f"{scheme}://{request.host}{endpoint}"

        content: bytes | None = None
        if request.body and request.body in arg_values:
            content = arg_values[request.body].encode("utf-8")

        client = await self._get_client()

        try:
            response = await client.request(
                request.method,
                url,
                headers=request.headers or None,
                content=content,
            )
        except httpx.HTTPError as exc:
            raise ExecutorError(f"request failed: {exc}") from exc

        body = response.text

        if response.status_code >= 400:
            raise ExecutorError(f"http request failed: {body}")

        return json.dumps(
            {"status_code": response.status_code, "body": body},
            separators=(",", ":"),
            ensure_ascii=False,
        )
