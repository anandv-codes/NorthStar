"""Route-level tests for the walked main path.

Pure-function tests cannot catch dependency-wiring bugs: a router mounted at
the wrong prefix, a dependency reading the wrong claim, or a response model
that rejects the repository's row shape. These are the journeys a user
actually walks, exercised through the real FastAPI app.

External services (Supabase, SQS, Gemini) are replaced at the route module
boundary, so the tests stay offline and fast while still covering the wiring.
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.api.deps import get_current_user_id
from backend.app.api.routes import auth as auth_routes
from backend.app.api.routes import chat as chat_routes
from backend.app.api.routes import notes as notes_routes
from backend.app.infrastructure.auth import jwt_service
from backend.app.main import app

USER = "user-1"
PASSWORD = "correct-horse1"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("WARMUP_ON_STARTUP", "false")
    app.dependency_overrides[get_current_user_id] = lambda: USER
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# -- POST /notes: create -> 202 -> status ---------------------------------


def test_create_note_returns_202_then_status_is_pollable(client, monkeypatch):
    saved: dict = {}
    monkeypatch.setattr(notes_routes, "PROCESS_NOTES_INLINE", False)
    monkeypatch.setattr(notes_routes, "put_note_item", lambda item: saved.update(item))
    monkeypatch.setattr(notes_routes, "send_note_job", lambda job: saved.update(job))

    response = client.post("/notes", json={"text": "ship the thing"})

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "processing"
    note_id = body["note_id"]
    # The job handed to SQS must carry the same note id the client polls.
    assert saved["note_id"] == note_id
    assert saved["user_id"] == USER

    monkeypatch.setattr(
        notes_routes,
        "get_note_item",
        lambda user_id, note_id: {
            "note_id": note_id,
            "user_id": user_id,
            "status": "processing",
            "created_at": _now(),
            "raw_text": "ship the thing",
        },
    )
    status_response = client.get(f"/notes/{note_id}")

    assert status_response.status_code == 200
    assert status_response.json()["status"] == "processing"


def test_create_note_requires_auth(monkeypatch):
    # No dependency override: the real bearer check must reject anonymous calls.
    monkeypatch.setenv("WARMUP_ON_STARTUP", "false")
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        response = test_client.post("/notes", json={"text": "anonymous"})
    assert response.status_code == 401


# -- /auth/login and /auth/refresh ----------------------------------------


def _fake_user(*, is_active: bool = True) -> dict:
    return {
        "user_id": USER,
        "email": "anand@example.com",
        "password_hash": jwt_service.hash_password(PASSWORD),
        "is_active": is_active,
    }


def test_login_rejects_bad_password(client, monkeypatch):
    monkeypatch.setattr(auth_routes, "get_user_by_email", lambda email: _fake_user())

    response = client.post(
        "/auth/login", json={"email": "anand@example.com", "password": "wrong-pass1"}
    )

    assert response.status_code == 401


def test_login_rejects_inactive_user(client, monkeypatch):
    monkeypatch.setattr(
        auth_routes, "get_user_by_email", lambda email: _fake_user(is_active=False)
    )

    response = client.post(
        "/auth/login", json={"email": "anand@example.com", "password": PASSWORD}
    )

    assert response.status_code == 403


def test_login_issues_access_token(client, monkeypatch):
    monkeypatch.setattr(auth_routes, "get_user_by_email", lambda email: _fake_user())
    monkeypatch.setattr(jwt_service, "JWT_SECRET_KEY", "test-secret")

    response = client.post(
        "/auth/login", json={"email": "anand@example.com", "password": PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_refresh_is_gone(client):
    response = client.post("/auth/refresh")
    assert response.status_code == 410


# -- POST /chat/message happy path ----------------------------------------


def test_chat_message_happy_path(client, monkeypatch):
    now = _now()
    thread = {
        "thread_id": "thread-1",
        "user_id": USER,
        "title": "Hello",
        "summary": None,
        "summary_updated_at": None,
        "created_at": now,
        "updated_at": now,
    }

    def message(role: str, content: str) -> dict:
        return {
            "message_id": f"msg-{role}",
            "thread_id": "thread-1",
            "user_id": USER,
            "role": role,
            "content": content,
            "intent": None,
            "metadata": {},
            "created_at": now,
        }

    monkeypatch.setattr(
        chat_routes,
        "handle_chat_message",
        lambda **kwargs: {
            "thread": thread,
            "user_message": message("user", kwargs["message"]),
            "assistant_message": message("assistant", "Here is your answer."),
            "intent": {"kind": "direct", "confidence": 0.9},
        },
    )

    response = client.post("/chat/message", json={"message": "what is on my plate?"})

    assert response.status_code == 200
    body = response.json()
    assert body["thread"]["thread_id"] == "thread-1"
    assert body["user_message"]["content"] == "what is on my plate?"
    assert body["assistant_message"]["content"] == "Here is your answer."
