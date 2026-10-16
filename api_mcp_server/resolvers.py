"""Per-type argument resolution.

Port of ``pkg/resolver/resolvers.go``. Each resolver turns a raw JSON argument
into the string form used inside the HTTP request, and contributes the JSON
Schema property advertised to the client.
"""

from __future__ import annotations

from typing import Any

from .models import Arg


class ResolverError(ValueError):
    """Raised when an argument cannot be resolved."""


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


class Resolver:
    """Base resolver."""

    json_type = "string"

    def resolve(self, arguments: dict[str, Any], arg: Arg) -> str:  # pragma: no cover
        raise NotImplementedError

    def tool_property(self, arg: Arg) -> dict[str, Any]:
        prop: dict[str, Any] = {"type": self.json_type}
        if arg.description:
            prop["description"] = arg.description
        return prop

    @staticmethod
    def _present(arguments: dict[str, Any], name: str) -> bool:
        return name in arguments and arguments[name] is not None


class StringResolver(Resolver):
    json_type = "string"

    def resolve(self, arguments: dict[str, Any], arg: Arg) -> str:
        if arg.required:
            if not self._present(arguments, arg.name):
                raise ResolverError("is required")
            value = arguments[arg.name]
            if not isinstance(value, str):
                raise ResolverError("is not a string")
            return value

        value = arguments.get(arg.name)
        if isinstance(value, str):
            return value
        default = arg.default_value if isinstance(arg.default_value, str) else ""
        return default


class IntResolver(Resolver):
    json_type = "integer"

    def resolve(self, arguments: dict[str, Any], arg: Arg) -> str:
        if arg.required:
            if not self._present(arguments, arg.name):
                raise ResolverError("is required")
            value = _as_int(arguments[arg.name])
            if value is None:
                raise ResolverError("is not an integer")
            return str(value)

        value = _as_int(arguments.get(arg.name))
        if value is None:
            value = _as_int(arg.default_value) or 0
        return str(value)


class FloatResolver(Resolver):
    json_type = "number"

    def resolve(self, arguments: dict[str, Any], arg: Arg) -> str:
        if arg.required:
            if not self._present(arguments, arg.name):
                raise ResolverError("is required")
            value = _as_float(arguments[arg.name])
            if value is None:
                raise ResolverError("is not a number")
            return f"{value:.6f}"

        value = _as_float(arguments.get(arg.name))
        if value is None:
            value = _as_float(arg.default_value)
        if value is None:
            value = 0.0
        return f"{value:.6f}"


class BoolResolver(Resolver):
    json_type = "boolean"

    def resolve(self, arguments: dict[str, Any], arg: Arg) -> str:
        if arg.required:
            if not self._present(arguments, arg.name):
                raise ResolverError("is required")
            value = arguments[arg.name]
            if not isinstance(value, bool):
                raise ResolverError("is not a boolean")
            return "true" if value else "false"

        value = arguments.get(arg.name)
        if isinstance(value, bool):
            return "true" if value else "false"
        default = arg.default_value if isinstance(arg.default_value, bool) else False
        return "true" if default else "false"


class ResolverRegistry:
    """Maps an argument ``type`` to a :class:`Resolver`, defaulting to string."""

    def __init__(self) -> None:
        self._resolvers: dict[str, Resolver] = {
            "string": StringResolver(),
            "int": IntResolver(),
            "float": FloatResolver(),
            "bool": BoolResolver(),
        }

    def register(self, arg_type: str, resolver: Resolver) -> None:
        self._resolvers[arg_type] = resolver

    def get(self, arg_type: str) -> Resolver:
        return self._resolvers.get(arg_type, self._resolvers["string"])

    def resolve(self, arguments: dict[str, Any], arg: Arg) -> str:
        return self.get(arg.type).resolve(arguments, arg)

    def tool_property(self, arg: Arg) -> dict[str, Any]:
        return self.get(arg.type).tool_property(arg)
