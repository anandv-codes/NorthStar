"""Task status transition rules used by chat lifecycle tools."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from backend.app.infrastructure.db import memory_repository
from backend.app.infrastructure.db.memory_repository import (
    TASK_STATUS_TRANSITIONS,
    SupabaseMemoryRepository,
    _validate_transition,
)


class _FakeTaskTable:
    def __init__(self, current: dict[str, Any] | None) -> None:
        self.current = current
        self.operation = ""
        self.payload: dict[str, Any] = {}

    def select(self, *_args: Any, **_kwargs: Any) -> "_FakeTaskTable":
        self.operation = "select"
        return self

    def update(self, payload: dict[str, Any]) -> "_FakeTaskTable":
        self.operation = "update"
        self.payload = payload
        return self

    def eq(self, *_args: Any, **_kwargs: Any) -> "_FakeTaskTable":
        return self

    def limit(self, *_args: Any, **_kwargs: Any) -> "_FakeTaskTable":
        return self

    def execute(self) -> SimpleNamespace:
        if self.operation == "select":
            rows = [dict(self.current)] if self.current is not None else []
            return SimpleNamespace(data=rows)
        assert self.current is not None
        return SimpleNamespace(data=[{**self.current, **self.payload}])


class _FakeSupabase:
    def __init__(self, table: _FakeTaskTable) -> None:
        self.task_table = table

    def table(self, _name: str) -> _FakeTaskTable:
        return self.task_table


@pytest.mark.parametrize(
    ("current", "next_status"),
    [
        ("open", "in_progress"),
        ("open", "completed"),
        ("open", "archived"),
        ("in_progress", "open"),
        ("in_progress", "completed"),
        ("in_progress", "archived"),
        ("completed", "open"),
        ("completed", "archived"),
        ("archived", "open"),
    ],
)
def test_allowed_task_transitions(current: str, next_status: str) -> None:
    _validate_transition(
        current_status=current,
        next_status=next_status,
        transitions=TASK_STATUS_TRANSITIONS,
        item_type="task",
    )


@pytest.mark.parametrize(
    ("current", "next_status"),
    [
        ("completed", "in_progress"),
        ("archived", "in_progress"),
        ("archived", "completed"),
    ],
)
def test_blocked_task_transitions(current: str, next_status: str) -> None:
    with pytest.raises(ValueError, match="Invalid task status transition"):
        _validate_transition(
            current_status=current,
            next_status=next_status,
            transitions=TASK_STATUS_TRANSITIONS,
            item_type="task",
        )


def test_same_task_status_is_idempotent() -> None:
    _validate_transition(
        current_status="completed",
        next_status="completed",
        transitions=TASK_STATUS_TRANSITIONS,
        item_type="task",
    )


def test_completing_open_task_sets_completed_at(monkeypatch: pytest.MonkeyPatch) -> None:
    table = _FakeTaskTable(
        {"task_id": "t1", "user_id": "u1", "status": "open", "completed_at": None}
    )
    monkeypatch.setattr(memory_repository, "supabase", _FakeSupabase(table))

    result = SupabaseMemoryRepository().update_task_item(
        "u1", "t1", {"status": "completed"}
    )

    assert result["status"] == "completed"
    assert table.payload["completed_at"]


def test_completing_completed_task_preserves_completed_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    table = _FakeTaskTable(
        {
            "task_id": "t1",
            "user_id": "u1",
            "status": "completed",
            "completed_at": "2026-01-01T00:00:00+00:00",
        }
    )
    monkeypatch.setattr(memory_repository, "supabase", _FakeSupabase(table))

    SupabaseMemoryRepository().update_task_item("u1", "t1", {"status": "completed"})

    assert "completed_at" not in table.payload


def test_repository_rejects_blocked_transition(monkeypatch: pytest.MonkeyPatch) -> None:
    table = _FakeTaskTable(
        {"task_id": "t1", "user_id": "u1", "status": "completed", "completed_at": "x"}
    )
    monkeypatch.setattr(memory_repository, "supabase", _FakeSupabase(table))

    with pytest.raises(ValueError, match="Invalid task status transition"):
        SupabaseMemoryRepository().update_task_item(
            "u1", "t1", {"status": "in_progress"}
        )


def test_repository_missing_task_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(memory_repository, "supabase", _FakeSupabase(_FakeTaskTable(None)))

    assert SupabaseMemoryRepository().update_task_item(
        "u1", "missing", {"status": "completed"}
    ) == {}
