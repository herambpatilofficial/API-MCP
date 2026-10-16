"""Optional Bearer-token authentication for the SSE transport.

Port of ``internal/auth/auth.go``. When ``API_MCP_SSE_API_KEY`` is unset the
endpoint is open. The token comparison is constant-time.
"""

from __future__ import annotations

import hmac

BEARER_PREFIX = "Bearer "


class AuthError(Exception):
    """Raised when a request is not authorized."""


class Authenticator:
    def __init__(self, transport: str, api_key: str | None = None) -> None:
        self.transport = transport
        self.api_key = api_key or ""

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def verify(self, authorization_header: str | None) -> None:
        """Raise :class:`AuthError` if the header does not carry the API key.

        Does nothing when no key is configured or when using the stdio transport.
        """
        if self.transport == "stdio" or not self.api_key:
            return

        if not authorization_header:
            raise AuthError("missing Authorization header")

        token = (
            authorization_header[len(BEARER_PREFIX) :]
            if authorization_header.startswith(BEARER_PREFIX)
            else ""
        )
        if not token:
            raise AuthError("empty token in Authorization header")

        if not hmac.compare_digest(self.api_key, token):
            raise AuthError("invalid auth token")
