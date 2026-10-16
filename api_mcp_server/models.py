"""Typed representations of the JSON tool configuration.

Mirrors the Go structs in ``pkg/types/types.go`` of AdamShannag/api-mcp-server.
The JSON keys are camelCase (``pathParams``, ``queryParams``, ``defaultValue``)
but snake_case aliases are accepted as well for convenience.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _first(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return default


@dataclass(slots=True)
class Arg:
    """An input collected from the LLM for a tool."""

    name: str
    type: str = "string"
    description: str = ""
    required: bool = False
    default_value: Any = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Arg":
        if not isinstance(data, dict) or not data.get("name"):
            raise ValueError("tool argument is missing required field 'name'")
        return cls(
            name=str(data["name"]),
            type=str(data.get("type") or "string"),
            description=str(data.get("description") or ""),
            required=bool(data.get("required", False)),
            default_value=_first(data, "defaultValue", "default_value", "default"),
        )


@dataclass(slots=True)
class Request:
    """The HTTP request a tool performs."""

    host: str
    endpoint: str
    method: str = "GET"
    secure: bool = False
    headers: dict[str, str] = field(default_factory=dict)
    path_params: list[str] = field(default_factory=list)
    query_params: list[str] = field(default_factory=list)
    body: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Request":
        if not isinstance(data, dict):
            raise ValueError("'request' must be a JSON object")
        raw_headers = data.get("headers") or {}
        if not isinstance(raw_headers, dict):
            raise ValueError("'request.headers' must be a JSON object")
        return cls(
            host=str(data.get("host") or ""),
            endpoint=str(data.get("endpoint") or ""),
            method=str(data.get("method") or "GET").upper(),
            secure=bool(data.get("secure", False)),
            headers={str(k): str(v) for k, v in raw_headers.items()},
            path_params=[str(p) for p in (_first(data, "pathParams", "path_params", default=[]) or [])],
            query_params=[str(p) for p in (_first(data, "queryParams", "query_params", default=[]) or [])],
            body=str(data.get("body") or ""),
        )


@dataclass(slots=True)
class Tool:
    """A single MCP tool backed by an HTTP request."""

    name: str
    description: str
    args: list[Arg]
    request: Request

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Tool":
        if not isinstance(data, dict) or not data.get("name"):
            raise ValueError("tool is missing required field 'name'")
        request = data.get("request")
        if not isinstance(request, dict):
            raise ValueError(f"tool {data['name']!r} is missing a 'request' object")
        raw_args = data.get("args") or []
        if not isinstance(raw_args, list):
            raise ValueError(f"tool {data['name']!r}: 'args' must be a JSON array")
        return cls(
            name=str(data["name"]),
            description=str(data.get("description") or ""),
            args=[Arg.from_dict(a) for a in raw_args],
            request=Request.from_dict(request),
        )
