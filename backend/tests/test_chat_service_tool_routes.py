"""Chat service branch tests for read tools versus confirmation-gated writes."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from backend.app.domain.chat import services


class _FakePendingRepo:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []

    def get_latest_pending_action(self, **_kwargs: Any) -> None:
        return None

    def create_pending_action(self, **kwargs: Any) -> dict[str, Any]:
        self.created.append(kwargs)
        return {"pending_action_id": "pending-1"}


class _FakeOrchestrator:
    def __init__(self, outcome: SimpleNamespace) -> None:
        self.outcome = outcome

    def route(self, _context: Any) -> SimpleNamespace:
        return self.outcome


def _outcome(
    *,
    intent_kind: str,
    assistant_message: str,
    tool_name: str | None = None,
) -> SimpleNamespace:
    decision = SimpleNamespace(
        route="tool",
        intent_kind=intent_kind,
        confidence=0.9,
        allow_answer=True,
        grounding_mode="none",
        reasons=[f"{intent_kind}:test"],
        source_refs=[],
        fallback_message=None,
        tool_name=tool_name,
    )
    return SimpleNamespace(
        decision=decision,
        assistant_message=assistant_message,
        metadata={
            "intent": {
                "kind": intent_kind,
                "confidence": 0.9,
                "needs_retrieval": False,
                "needs_tools": intent_kind in {"action", "tool_read"},
                "direct_answer": False,
                "grounding_mode": "none",
                "reasons": [f"{intent_kind}:test"],
                "tool_name": tool_name,
            },
            "route": "tool",
            "tool_name": tool_name,
            "plan": [],
            "grounding": None,
            "knowledge_error": None,
        },
    )


@pytest.fixture
def service_stubs(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    stored: list[dict[str, Any]] = []

    monkeypatch.setattr(
        services,
        "ensure_chat_thread",
        lambda **_kwargs: {
            "thread_id": "thread-1",
            "title": "Test",
            "summary": None,
            "summary_updated_at": None,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        },
    )

    def store_message(**kwargs: Any) -> dict[str, Any]:
        row = {
            **kwargs,
            "message_id": f"msg-{len(stored) + 1}",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        stored.append(row)
        return row

    monkeypatch.setattr(services, "store_chat_message", store_message)
    monkeypatch.setattr(services, "load_recent_chat_messages", lambda **_kwargs: [])
    monkeypatch.setattr(services, "refresh_thread_summary", lambda **_kwargs: "")
    return stored


def _run_message(
    monkeypatch: pytest.MonkeyPatch,
    outcome: SimpleNamespace,
    pending_repo: _FakePendingRepo,
) -> dict[str, Any]:
    monkeypatch.setattr(services, "CHAT_ROUTING_ORCHESTRATOR", _FakeOrchestrator(outcome))
    return services.handle_chat_message(
        user_id="u1",
        message="what am I forgetting",
        thread_id="thread-1",
        repo=object(),
        pending_repo=pending_repo,
    )


def test_tool_read_never_proposes_pending_action(
    monkeypatch: pytest.MonkeyPatch, service_stubs: list[dict[str, Any]]
) -> None:
    pending_repo = _FakePendingRepo()

    def fail_resolve(**_kwargs: Any) -> None:
        raise AssertionError("read tools must not invoke write-tool resolution")

    monkeypatch.setattr(services, "resolve_tool_call", fail_resolve)

    response = _run_message(
        monkeypatch,
        _outcome(
            intent_kind="tool_read",
            assistant_message="Open loops: 1 open task.",
            tool_name="get_open_loops",
        ),
        pending_repo,
    )

    assert response["pending_action"] is None
    assert pending_repo.created == []
    assert response["routing"]["tool_name"] == "get_open_loops"
    assert response["intent"]["kind"] == "tool_read"
    assert response["assistant_message"]["content"] == "Open loops: 1 open task."
    assert service_stubs[-1]["intent"] == "tool_read"


def test_action_proposes_confirmation_gated_write(
    monkeypatch: pytest.MonkeyPatch, service_stubs: list[dict[str, Any]]
) -> None:
    pending_repo = _FakePendingRepo()
    monkeypatch.setattr(
        services,
        "resolve_tool_call",
        lambda **_kwargs: SimpleNamespace(
            tool_name="start_task",
            args={"task_id": "t1"},
            description='mark the task "Ship auth fix" as in progress',
            confirmed_message='Done — I\'ve marked "Ship auth fix" as in progress.',
        ),
    )

    response = _run_message(
        monkeypatch,
        _outcome(intent_kind="action", assistant_message="I can help with that."),
        pending_repo,
    )

    assert response["pending_action"] == {
        "pending_action_id": "pending-1",
        "tool_name": "start_task",
        "description": 'mark the task "Ship auth fix" as in progress',
    }
    assert pending_repo.created[0]["tool_name"] == "start_task"
    assert response["assistant_message"]["content"].endswith("Should I go ahead? (yes/no)")
    assert service_stubs[-1]["intent"] == "action"


def test_action_without_resolved_tool_returns_limited_capability_copy(
    monkeypatch: pytest.MonkeyPatch, service_stubs: list[dict[str, Any]]
) -> None:
    pending_repo = _FakePendingRepo()
    monkeypatch.setattr(services, "resolve_tool_call", lambda **_kwargs: None)

    response = _run_message(
        monkeypatch,
        _outcome(intent_kind="action", assistant_message="I can help with that."),
        pending_repo,
    )

    assert pending_repo.created == []
    assert "can't make that change yet" in response["assistant_message"]["content"]
