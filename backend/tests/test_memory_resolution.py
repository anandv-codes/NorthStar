"""Contract tests for deterministic task-completion resolution.

The resolver previously completed every task that shared the top overlap score,
so one sentence could close unrelated tasks. These tests pin the tie rule and
the single return shape.
"""
from typing import Any

from backend.app.domain.memory.services import apply_deterministic_task_resolution

USER = "user-1"


class _Repo:
    def __init__(self, tasks: list[dict[str, Any]]) -> None:
        self.tasks = tasks
        self.completed: list[str] = []

    def query_tasks_for_user(self, user_id: str, status: str | None = None):
        return self.tasks

    def update_task_item(self, user_id: str, task_id: str, updates: dict[str, Any]):
        self.completed.append(task_id)
        return {"task_id": task_id, **updates}


def _tasks() -> list[dict[str, Any]]:
    return [
        {"task_id": "t1", "description": "deploy the staging cluster"},
        {"task_id": "t2", "description": "deploy the production cluster"},
    ]


def test_tied_top_score_completes_nothing():
    repo = _Repo(_tasks())

    result = apply_deterministic_task_resolution(
        user_id=USER,
        raw_text="Deploy cluster done",
        source_note_id="note-1",
        repo=repo,
    )

    assert result["updated_tasks"] == []
    assert result["diagnostics"]["selection_blocked_reason"] == "ambiguous_multiple_matches"
    assert repo.completed == []


def test_unique_top_score_completes_only_that_task():
    repo = _Repo(_tasks())

    result = apply_deterministic_task_resolution(
        user_id=USER,
        raw_text="Deploy staging cluster done",
        source_note_id="note-1",
        repo=repo,
    )

    assert [task["task_id"] for task in result["updated_tasks"]] == ["t1"]
    assert repo.completed == ["t1"]


def test_returns_dict_even_when_nothing_matches():
    repo = _Repo(_tasks())

    result = apply_deterministic_task_resolution(
        user_id=USER,
        raw_text="",
        source_note_id="note-1",
        repo=repo,
    )

    assert result == {
        "updated_tasks": [],
        "diagnostics": {
            "source_note_id": "note-1",
            "completion_detected": False,
            "note_tokens": [],
            "note_numbers": [],
            "open_task_count": 0,
            "candidate_matches": [],
            "top_score": None,
            "selected_task_ids": [],
            "selection_blocked_reason": "empty_note_text",
        },
    }
    assert repo.completed == []
