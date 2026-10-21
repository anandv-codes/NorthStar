"""Tests for the retrying Supabase HTTP client."""
import httpx
import pytest

from backend.app.infrastructure.db.supabase_http_client import SupabaseHttpClient

URL = "https://example.supabase.co/rest/v1/notes"


def _client(handler, retries: int = 2) -> SupabaseHttpClient:
    return SupabaseHttpClient(transport=httpx.MockTransport(handler), retries=retries)


def test_get_is_retried_after_server_disconnect():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        if len(calls) == 1:
            raise httpx.RemoteProtocolError("Server disconnected")
        return httpx.Response(200, json={"ok": True})

    with _client(handler) as client:
        response = client.get(URL)

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert calls == ["GET", "GET"]


@pytest.mark.parametrize("method", ["HEAD", "OPTIONS"])
def test_idempotent_methods_are_retried(method: str):
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        if len(calls) == 1:
            raise httpx.RemoteProtocolError("Server disconnected")
        return httpx.Response(200)

    with _client(handler) as client:
        client.request(method, URL)

    assert calls == [method, method]


def test_post_is_not_retried():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        raise httpx.RemoteProtocolError("Server disconnected")

    with _client(handler) as client:
        with pytest.raises(httpx.RemoteProtocolError):
            client.post(URL, json={"description": "a task"})

    assert calls == ["POST"]


def test_retries_are_exhausted_before_raising():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        raise httpx.RemoteProtocolError("Server disconnected")

    with _client(handler, retries=1) as client:
        with pytest.raises(httpx.RemoteProtocolError):
            client.get(URL)

    assert calls == ["GET", "GET"]


def test_non_transport_errors_are_not_retried():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        return httpx.Response(503, json={"message": "unavailable"})

    with _client(handler) as client:
        response = client.get(URL)

    assert response.status_code == 503
    assert calls == ["GET"]
