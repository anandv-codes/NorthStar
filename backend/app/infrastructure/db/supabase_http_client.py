"""HTTP client used for Supabase/PostgREST calls.

Supabase closes idle HTTP/2 connections server-side. The app keeps one
process-wide client, so a request can pick a connection the server has already
closed and fail with ``httpx.RemoteProtocolError("Server disconnected")``. The
repository layer only catches PostgREST ``APIError``, so that transport error
used to escape as an unhandled 500 (seen on ``GET /memory/recent``).

``SupabaseHttpClient`` retries the request once the dead connection has been
evicted from the pool. Only idempotent methods are retried: if the connection
drops after the server committed a ``POST``/``PATCH``, replaying it would
duplicate rows.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from postgrest.constants import DEFAULT_POSTGREST_CLIENT_TIMEOUT

logger = logging.getLogger(__name__)

#: Methods that are safe to replay if the connection dies mid-request.
RETRYABLE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

#: Number of extra attempts after the first one.
DEFAULT_RETRIES = 2


class SupabaseHttpClient(httpx.Client):
    """``httpx.Client`` that retries idempotent requests on a dead connection."""

    def __init__(self, *, retries: int = DEFAULT_RETRIES, **kwargs: Any) -> None:
        # Match the settings supabase-py's PostgREST client would use by default.
        kwargs.setdefault("http2", True)
        kwargs.setdefault("timeout", httpx.Timeout(DEFAULT_POSTGREST_CLIENT_TIMEOUT))
        kwargs.setdefault("follow_redirects", True)
        super().__init__(**kwargs)
        self.retries = max(0, retries)

    def send(
        self,
        request: httpx.Request,
        *,
        stream: bool = False,
        **kwargs: Any,
    ) -> httpx.Response:
        attempts = self.retries + 1 if request.method in RETRYABLE_METHODS else 1
        for attempt in range(1, attempts + 1):
            try:
                return super().send(request, stream=stream, **kwargs)
            except httpx.RemoteProtocolError as exc:
                if attempt >= attempts:
                    raise
                logger.warning(
                    "Supabase connection dropped during %s %s (attempt %d/%d); "
                    "retrying on a fresh connection: %s",
                    request.method,
                    request.url,
                    attempt,
                    attempts,
                    exc,
                )
        raise AssertionError("unreachable")  # pragma: no cover
