"""Wall-clock abstraction so scheduling is deterministic in tests."""
from __future__ import annotations

from datetime import datetime, timezone


class SystemClock:
    """Default ``Clock`` implementation using UTC."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)
