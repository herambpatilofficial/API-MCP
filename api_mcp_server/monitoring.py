"""Optional Prometheus metrics and health endpoint.

Port of ``internal/monitoring/monitoring.go``. Uses ``prometheus-client`` when
installed; otherwise all methods are no-ops so the server still runs.
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

try:  # pragma: no cover - exercised indirectly
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    _HAS_PROMETHEUS = True
except Exception:  # pragma: no cover
    _HAS_PROMETHEUS = False

_NAMESPACE = "api_mcp_server"


def _exponential_buckets(start: float, factor: float, count: int) -> tuple[float, ...]:
    return tuple(start * (factor**i) for i in range(count))


class Metrics:
    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled and _HAS_PROMETHEUS
        self._httpd: ThreadingHTTPServer | None = None

        if self.enabled:
            self.registry = CollectorRegistry()
            self.tool_invocations = Counter(
                f"{_NAMESPACE}_tool_invocations_total",
                "Total number of tool invocations",
                ["tool"],
                registry=self.registry,
            )
            self.tool_latency = Histogram(
                f"{_NAMESPACE}_tool_duration_seconds",
                "Tool execution duration in seconds",
                ["tool"],
                buckets=_exponential_buckets(0.01, 2, 12),
                registry=self.registry,
            )
            self.session_starts = Counter(
                f"{_NAMESPACE}_session_starts_total",
                "Total number of sessions started",
                registry=self.registry,
            )
            self.session_closes = Counter(
                f"{_NAMESPACE}_session_closes_total",
                "Total number of sessions closed",
                registry=self.registry,
            )
            self.active_sessions = Gauge(
                f"{_NAMESPACE}_active_sessions",
                "Current number of active sessions",
                registry=self.registry,
            )
            self.errors_total = Counter(
                f"{_NAMESPACE}_errors_total",
                "Total number of errors encountered per method",
                ["method"],
                registry=self.registry,
            )

    def tool_invocation(self, tool: str) -> None:
        if self.enabled:
            self.tool_invocations.labels(tool).inc()

    def tool_latency_observe(self, tool: str, seconds: float) -> None:
        if self.enabled:
            self.tool_latency.labels(tool).observe(seconds)

    def session_start(self) -> None:
        if self.enabled:
            self.session_starts.inc()
            self.active_sessions.inc()

    def session_close(self) -> None:
        if self.enabled:
            self.session_closes.inc()
            self.active_sessions.dec()

    def error(self, method: str) -> None:
        if self.enabled:
            self.errors_total.labels(method).inc()

    def start_server(self, port: int) -> None:
        if not self.enabled or self._httpd is not None:
            return

        registry = self.registry

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/healthz":
                    self._respond(200, b"ok", "text/plain")
                elif self.path == "/metrics":
                    self._respond(200, generate_latest(registry), CONTENT_TYPE_LATEST)
                else:
                    self._respond(404, b"not found", "text/plain")

            def _respond(self, status: int, body: bytes, content_type: str) -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args: Any) -> None:  # silence default logging
                return

        self._httpd = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
