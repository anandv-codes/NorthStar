import json
from types import SimpleNamespace

from backend.app import observability as obs


def test_build_request_timing_payload_uses_route_template():
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/recall/cards/abc",
        "route": SimpleNamespace(path="/recall/cards/{card_id}"),
    }

    payload = obs.build_request_timing_payload(scope, 200, 12.36)

    assert payload == {
        "method": "GET",
        "route": "/recall/cards/{card_id}",
        "path": "/recall/cards/abc",
        "status": 200,
        "duration_ms": 12.4,
    }


def test_build_request_timing_payload_falls_back_to_path():
    scope = {"type": "http", "method": "GET", "path": "/missing"}

    payload = obs.build_request_timing_payload(scope, 404, 1.0)

    assert payload["route"] == "/missing"
    assert payload["status"] == 404


def test_log_timing_event_writes_one_json_line(monkeypatch):
    captured: list[str] = []
    monkeypatch.setattr(obs._timing_logger, "info", captured.append)

    obs.log_timing_event("request_timing", duration_ms=12.3, success=True)

    assert len(captured) == 1
    payload = json.loads(captured[0])
    assert payload["event"] == "request_timing"
    assert payload["duration_ms"] == 12.3
    assert payload["success"] is True
    assert "timestamp" in payload
