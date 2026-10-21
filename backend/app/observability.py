"""Structured latency events for the API and background workers."""
from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, MutableMapping

logger = logging.getLogger(__name__)

_timing_logger = logging.getLogger("northstar.timing")
if not _timing_logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _timing_logger.addHandler(_handler)
    _timing_logger.setLevel(logging.INFO)
    _timing_logger.propagate = False


def log_timing_event(event: str, **fields: Any) -> None:
    """Write one JSON timing event without the usual log-line prefix."""
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    try:
        _timing_logger.info(json.dumps(payload, default=str))
    except Exception:
        logger.debug("Failed to write timing event", exc_info=True)


def build_request_timing_payload(
    scope: MutableMapping[str, Any],
    status: int,
    duration_ms: float,
) -> dict[str, Any]:
    """Build the request-timing fields from an ASGI scope."""
    route = scope.get("route")
    return {
        "method": scope.get("method"),
        "route": getattr(route, "path", None) or scope.get("path"),
        "path": scope.get("path"),
        "status": status,
        "duration_ms": round(duration_ms, 1),
    }


class RequestTimingMiddleware:
    """Measure the full HTTP response, including the response body."""

    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Callable, send: Callable) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()
        status = 500

        async def send_wrapper(message: dict[str, Any]) -> None:
            nonlocal status
            if message.get("type") == "http.response.start":
                status = int(message.get("status", 500))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            log_timing_event(
                "request_timing",
                **build_request_timing_payload(scope, status, duration_ms),
            )


def install_request_timing(app: Any) -> None:
    """Register the timing middleware on a FastAPI/Starlette application."""
    app.add_middleware(RequestTimingMiddleware)
