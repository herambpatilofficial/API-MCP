"""MCP server wiring.

Port of ``internal/mcp/server.go``: loads tools dynamically, exposes them via
the ``tools/list`` and ``tools/call`` MCP methods, and supports the ``stdio``
and ``sse`` transports.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server

from .auth import AuthError, Authenticator
from .config import load_tools
from .executor import ExecutorError, HttpExecutor
from .models import Tool
from .monitoring import Metrics
from .resolvers import ResolverError, ResolverRegistry

SERVER_NAME = "API MCP Server"
VERSION = "0.2.0"

logger = logging.getLogger("api_mcp_server")


class ApiMcpServer:
    def __init__(
        self,
        transport: str = "stdio",
        tools_file: str = "./config.json",
        host: str = "127.0.0.1",
        port: int = 13080,
        auth: Authenticator | None = None,
        metrics: Metrics | None = None,
        executor: HttpExecutor | None = None,
    ) -> None:
        self.transport = transport
        self.tools_file = tools_file
        self.host = host
        self.port = port
        self.auth = auth or Authenticator(transport)
        self.metrics = metrics or Metrics(enabled=False)
        self.executor = executor or HttpExecutor()
        self.resolvers = ResolverRegistry()
        self.tools: dict[str, Tool] = {}

        self.server: Server = Server(SERVER_NAME, version=VERSION)
        self._register_handlers()

    # ------------------------------------------------------------------ setup

    def load_tools(self) -> int:
        tools = load_tools(self.tools_file)
        for tool in tools:
            self.tools[tool.name] = tool
        logger.info("tools loaded: %d", len(tools))
        return len(tools)

    def _register_handlers(self) -> None:
        @self.server.list_tools()
        async def _list_tools() -> list[types.Tool]:
            return [self._to_mcp_tool(tool) for tool in self.tools.values()]

        @self.server.call_tool(validate_input=False)
        async def _call_tool(
            name: str, arguments: dict[str, Any]
        ) -> types.CallToolResult:
            return await self._handle_call(name, arguments or {})

    def _to_mcp_tool(self, tool: Tool) -> types.Tool:
        properties: dict[str, Any] = {}
        required: list[str] = []
        for arg in tool.args:
            properties[arg.name] = self.resolvers.tool_property(arg)
            if arg.required:
                required.append(arg.name)

        schema: dict[str, Any] = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required

        return types.Tool(
            name=tool.name,
            description=tool.description or None,
            inputSchema=schema,
        )

    # ---------------------------------------------------------------- handler

    async def _handle_call(
        self, name: str, arguments: dict[str, Any]
    ) -> types.CallToolResult:
        tool = self.tools.get(name)
        if tool is None:
            return self._error_result(f"unknown tool: {name}")

        arg_values: dict[str, str] = {}
        for arg in tool.args:
            try:
                arg_values[arg.name] = self.resolvers.resolve(arguments, arg)
            except ResolverError as exc:
                return self._error_result(f'invalid argument "{arg.name}": {exc}')

        self.metrics.tool_invocation(name)
        started = time.perf_counter()
        try:
            body = await self.executor.execute(tool.request, arg_values)
        except ExecutorError as exc:
            logger.error("tool %s failed: %s", name, exc)
            self.metrics.error(name)
            return self._error_result(f"request failed: {exc}")
        finally:
            self.metrics.tool_latency_observe(name, time.perf_counter() - started)

        return types.CallToolResult(
            content=[types.TextContent(type="text", text=body)]
        )

    @staticmethod
    def _error_result(message: str) -> types.CallToolResult:
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=message)],
            isError=True,
        )

    # ------------------------------------------------------------------- run

    async def run(self) -> None:
        try:
            if self.transport == "sse":
                await self._run_sse()
            else:
                await self._run_stdio()
        finally:
            await self.executor.aclose()

    async def _run_stdio(self) -> None:
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(
                    notification_options=NotificationOptions()
                ),
                stateless=False,
            )

    def _build_sse_app(self) -> Any:
        from mcp.server.sse import SseServerTransport
        from mcp.server.transport_security import TransportSecuritySettings
        from starlette.applications import Starlette
        from starlette.routing import Mount, Route

        transport = SseServerTransport(
            "/messages/",
            security_settings=TransportSecuritySettings(
                enable_dns_rebinding_protection=False
            ),
        )
        server = self.server

        async def handle_sse(request):  # pragma: no cover - network
            async with transport.connect_sse(
                request.scope, request.receive, request._send
            ) as (read_stream, write_stream):
                await server.run(
                    read_stream,
                    write_stream,
                    server.create_initialization_options(
                        notification_options=NotificationOptions()
                    ),
                    stateless=False,
                )

        app = Starlette(
            routes=[
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=transport.handle_post_message),
            ]
        )
        return _BearerAuthASGI(app, self.auth)

    async def _run_sse(self) -> None:  # pragma: no cover - network
        import uvicorn

        config = uvicorn.Config(
            self._build_sse_app(),
            host=self.host,
            port=self.port,
            log_level="info",
        )
        uvicorn_server = uvicorn.Server(config)
        logger.info("sse server started on %s:%s", self.host, self.port)
        await uvicorn_server.serve()


class _BearerAuthASGI:
    """ASGI wrapper enforcing Bearer auth before delegating to the app."""

    def __init__(self, app: Any, auth: Authenticator) -> None:
        self.app = app
        self.auth = auth

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") == "http" and self.auth.enabled:
            raw = dict(scope.get("headers") or []).get(b"authorization")
            header = raw.decode("latin-1") if raw else None
            try:
                self.auth.verify(header)
            except AuthError as exc:
                from starlette.responses import Response

                await Response(str(exc), status_code=401)(scope, receive, send)
                return
        await self.app(scope, receive, send)
