"""Loading of the tool configuration file.

Faithful port of the environment placeholder resolution and JSON decoding
performed by ``internal/mcp/server.go`` in the Go original.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping

from .models import Tool

PLACEHOLDER_PREFIX = "{{env "
PLACEHOLDER_SUFFIX = "}}"


def resolve_env_placeholders(
    text: str, environ: Mapping[str, str] | None = None
) -> str:
    """Resolve ``{{env VAR_NAME:default_value}}`` placeholders.

    An environment variable is only used when it is set and non-empty,
    otherwise the default value is substituted. This matches the Go
    implementation exactly.
    """
    env = os.environ if environ is None else environ
    out: list[str] = []
    i = 0
    length = len(text)

    while i < length:
        start = text.find(PLACEHOLDER_PREFIX, i)
        if start == -1:
            out.append(text[i:])
            break

        out.append(text[i:start])

        end = text.find(PLACEHOLDER_SUFFIX, start)
        if end == -1:
            out.append(text[start:])
            break

        content = text[start + len(PLACEHOLDER_PREFIX) : end].strip()
        var_name = content
        default_value = ""

        sep = content.find(":")
        if sep != -1:
            var_name = content[:sep].strip()
            default_value = content[sep + 1 :].strip()

        value = env.get(var_name, "")
        out.append(value if value else default_value)
        i = end + len(PLACEHOLDER_SUFFIX)

    return "".join(out)


def load_tools(
    path: str | os.PathLike[str], environ: Mapping[str, str] | None = None
) -> list[Tool]:
    """Read, resolve and decode a tool configuration file into ``Tool`` objects."""
    config_path = Path(path)
    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"failed to read file: {exc}") from exc

    resolved = resolve_env_placeholders(raw, environ)

    try:
        data = json.loads(resolved)
    except json.JSONDecodeError as exc:
        raise ValueError(f"failed to decode JSON: {exc}") from exc

    if not isinstance(data, list):
        raise ValueError("tool config must be a JSON array of tools")

    tools: list[Tool] = []
    seen: set[str] = set()
    for item in data:
        tool = Tool.from_dict(item)
        if tool.name in seen:
            raise ValueError(f"duplicate tool name: {tool.name!r}")
        seen.add(tool.name)
        tools.append(tool)
    return tools
