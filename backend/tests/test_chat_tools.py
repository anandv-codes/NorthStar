"""Unit tests for confirmation-gated chat write tools."""
from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from backend.app.domain.chat import tools
from backend.app.domain.chat.tool_resolver import execute_tool_call


def test_question_and_concept_tools_remain_disabled() -> None:
    assert "create_question" not in tools.ENABLED_TOOL_NAMES
    assert "answer_question" not in tools.ENABLED_TOOL_NAMES
    assert "create_concept" not in tools.ENABLED_TOOL_NAMES
    assert "mark_concept_learned" not in tools.ENABLED_TOOL_NAMES


def test_lifecycle_and_goal_tools_are_enabled() -> None:
    assert {
        "start_task",
        "reopen_task",
        "archive_task",
        "update_commitment_progress",
    }.issubset(tools.ENABLED_TOOL_NAMES)


def test_tool_context_includes_task_views_and_goals(monkeypatch: pytest.MonkeyPatch) -> None:
    tasks_by_status = {
        "open": [{"task_id": "t-open", "description": "Draft launch note"}],
        "in_progress": [{"task_id": "t-progress", "description": "Ship auth fix"}],
        "completed": [{"task_id": "t-done", "description": "Review deploy"}],
        "archived": [{"task_id": "t-archived", "description": "Old migration"}],
    }
    calls: list[str | None] = []

    def fake_tasks(user_id: str, status: str | None = None) -> list[dict[str, Any]]:
        calls.append(status)
        return tasks_by_status.get(str(status), [])

    monkeypatch.setattr(tools, "query_tasks_for_user", fake_tasks)
    monkeypatch.setattr(
        tools,
        "list_commitments",
        lambda user_id, status=None: [
            {"commitment_id": "g1", "text": "Learn distributed systems", "progress": 40}
        ],
    )

    context, lookup = tools.build_tool_context("u1")

    assert calls == ["open", "in_progress", "completed", "archived"]
    assert "Open tasks:" in context
    assert "In-progress tasks:" in context
    assert "Completed tasks:" in context
    assert "Archived tasks:" in context
    assert "Active goals:" in context
    assert "Learn distributed systems (40%)" in context
    assert "Open questions:" not in context
    assert "Open concepts:" not in context
    assert lookup["t-open"] == "Draft launch note"
    assert lookup["g1"] == "Learn distributed systems (40%)"


def test_start_task_executor_sets_in_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_update(user_id: str, task_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        captured.update({"user_id": user_id, "task_id": task_id, "updates": updates})
        return {"task_id": task_id, **updates}

    monkeypatch.setattr(tools, "update_task_item", fake_update)

    result = execute_tool_call("u1", "start_task", {"task_id": "t1"})

    assert result["status"] == "in_progress"
    assert captured == {
        "user_id": "u1",
        "task_id": "t1",
        "updates": {"status": "in_progress", "completed_at": None},
    }


def test_reopen_task_executor_clears_completed_at(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_update(user_id: str, task_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        captured.update(updates)
        return {"task_id": task_id, **updates}

    monkeypatch.setattr(tools, "update_task_item", fake_update)

    execute_tool_call("u1", "reopen_task", {"task_id": "t1"})

    assert captured == {"status": "open", "completed_at": None}


def test_archive_task_executor_sets_archived(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_update(user_id: str, task_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        captured.update(updates)
        return {"task_id": task_id, **updates}

    monkeypatch.setattr(tools, "update_task_item", fake_update)

    execute_tool_call("u1", "archive_task", {"task_id": "t1"})

    assert captured == {"status": "archived"}


def test_commitment_progress_executor(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_update(
        user_id: str, commitment_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        captured.update(
            {"user_id": user_id, "commitment_id": commitment_id, "updates": updates}
        )
        return {"commitment_id": commitment_id, **updates}

    monkeypatch.setattr(tools, "update_commitment", fake_update)

    result = execute_tool_call(
        "u1", "update_commitment_progress", {"commitment_id": "g1", "progress": 60}
    )

    assert result["progress"] == 60
    assert captured == {
        "user_id": "u1",
        "commitment_id": "g1",
        "updates": {"progress": 60},
    }


def test_commitment_progress_rejects_out_of_range() -> None:
    with pytest.raises(ValidationError):
        execute_tool_call(
            "u1", "update_commitment_progress", {"commitment_id": "g1", "progress": 101}
        )


def test_executor_with_no_result_is_reported_as_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tools, "update_task_item", lambda *_args, **_kwargs: {})

    with pytest.raises(ValueError, match="made no change"):
        execute_tool_call("u1", "complete_task", {"task_id": "missing"})
