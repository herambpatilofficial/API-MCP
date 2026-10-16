"""Command line interface.

Port of ``cmd/api-mcp-server/main.go``. Flags, environment variables and
defaults mirror the Go original.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from .auth import Authenticator
from .monitoring import Metrics
from .server import VERSION, ApiMcpServer

DEFAULT_SSE_HOST = "127.0.0.1"
DEFAULT_SSE_PORT = 13080
DEFAULT_METRICS_PORT = 8080

_LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARN": logging.WARNING,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}


def setup_logging(level_name: str | None) -> None:
    level = _LOG_LEVELS.get((level_name or "").upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-5s %(name)s %(message)s",
        stream=sys.stderr,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="api-mcp-server",
        description="Lightweight and extensible MCP server for defining and executing API tools.",
    )
    parser.add_argument(
        "-t",
        "--transport",
        default="stdio",
        choices=["stdio", "sse"],
        help="Transport type: stdio or sse (default: stdio)",
    )
    parser.add_argument(
        "-c",
        "--config",
        default="./config.json",
        help="Path to JSON tool configuration (default: ./config.json)",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="store_true",
        help="Show version and exit",
    )
    parser.add_argument(
        "-m",
        "--metrics",
        action="store_true",
        help="Enable Prometheus metrics and health check server",
    )
    parser.add_argument(
        "--metrics-port",
        default=str(DEFAULT_METRICS_PORT),
        help="Metrics and health check server port (default: 8080)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.version:
        print(f"api-mcp-server {VERSION}")
        return 0

    setup_logging(os.environ.get("LOG_LEVEL"))

    host = os.environ.get("API_MCP_HOST") or DEFAULT_SSE_HOST
    port = int(os.environ.get("API_MCP_PORT") or DEFAULT_SSE_PORT)

    auth = Authenticator(args.transport, os.environ.get("API_MCP_SSE_API_KEY"))
    metrics = Metrics(enabled=bool(args.metrics))
    if args.metrics:
        metrics.start_server(int(args.metrics_port))

    server = ApiMcpServer(
        transport=args.transport,
        tools_file=args.config,
        host=host,
        port=port,
        auth=auth,
        metrics=metrics,
    )

    try:
        server.load_tools()
    except ValueError as exc:
        logging.getLogger("api_mcp_server").error("%s", exc)
        return 1

    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:  # pragma: no cover - interactive
        pass
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
