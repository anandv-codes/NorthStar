"""Route-surface guards for the notes API.

These assert what the API deliberately does *not* expose. The queue-draining
debug route was a cross-tenant, cost-amplifying hole: any authenticated user
could make the API process other users' queued notes.
"""
from backend.app.main import app


def _route_paths() -> set[str]:
    return {getattr(route, "path", "") for route in app.routes}


def test_queue_draining_debug_route_is_gone():
    paths = _route_paths()
    assert "/notes/poll/process-jobs" not in paths
    # Catch a re-introduction under a different prefix.
    assert not [path for path in paths if "process-jobs" in path]
