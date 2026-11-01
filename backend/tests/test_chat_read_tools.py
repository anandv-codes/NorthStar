"""Unit tests for read-only chat tools."""
from __future__ import annotations

from typing import Any

import pytest

from backend.app.domain.chat import read_tools


class _FakeRecallRepo:
    def query_cards_page(self, *args: Any, **kwargs: Any) -> dict[str, int]:
        return {"total": 7}


def test_open_loops_read_tool_caps_items_and_excludes_questions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        read_tools,
        "query_tasks_for_user",
        lambda user_id, status=None: [
            {"task_id": f"{status}-{index}", "description": f"{status} task {index}"}
            for index in range(8)
        ],
    )
    monkeypatch.setattr(
        read_tools,
        "list_commitments",
        lambda user_id, status=None: [
            {"commitment_id": "g1", "text": "Learn systems", "progress": 40}
        ],
    )

    result = read_tools.execute_read_tool("u1", "get_open_loops")

    assert set(result) == {"counts", "tasks", "in_progress", "goals"}
    assert result["counts"] == {
        "open_tasks": 8,
        "in_progress_tasks": 8,
        "active_goals": 1,
    }
    assert len(result["tasks"]) == read_tools.MAX_READ_ITEMS
    assert len(result["in_progress"]) == read_tools.MAX_READ_ITEMS
    assert result["goals"] == [
        {"commitment_id": "g1", "text": "Learn systems", "progress": 40}
    ]

    rendered = read_tools.format_read_tool_result("get_open_loops", result)
    assert "Open loops: 8 open task(s), 8 in progress, 1 active goal(s)." in rendered
    assert "Learn systems (40%)" in rendered
    assert "question" not in rendered.lower()


def test_due_cards_read_tool_hides_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _FakeRecallRepo()
    monkeypatch.setattr(read_tools, "get_recall_repository", lambda: repo)
    monkeypatch.setattr(
        read_tools,
        "list_cards",
        lambda *args, **kwargs: [
            {
                "card_id": "c1",
                "deck_id": "d1",
                "question": "What is RRF?",
                "answer": "Reciprocal rank fusion",
                "next_due": "2026-10-29T10:00:00+00:00",
            }
        ],
    )

    result = read_tools.execute_read_tool("u1", "get_due_cards")
    rendered = read_tools.format_read_tool_result("get_due_cards", result)

    assert result["total_due"] == 7
    assert result["cards"] == [
        {
            "card_id": "c1",
            "deck_id": "d1",
            "question": "What is RRF?",
            "next_due": "2026-10-29T10:00:00+00:00",
        }
    ]
    assert "What is RRF?" in rendered
    assert "Reciprocal rank fusion" not in rendered


def test_read_tool_registry_is_limited_to_approved_views() -> None:
    assert set(read_tools.READ_TOOL_REGISTRY) == {"get_open_loops", "get_due_cards"}
    assert "get_open_questions" not in read_tools.ENABLED_READ_TOOL_NAMES
    assert "get_concepts" not in read_tools.ENABLED_READ_TOOL_NAMES


def test_empty_open_loops_render_an_empty_state() -> None:
    rendered = read_tools.format_read_tool_result(
        "get_open_loops",
        {
            "counts": {"open_tasks": 0, "in_progress_tasks": 0, "active_goals": 0},
            "tasks": [],
            "in_progress": [],
            "goals": [],
        },
    )

    assert "There are no open tasks, in-progress tasks, or active goals." in rendered


def test_empty_due_cards_render_an_empty_state() -> None:
    rendered = read_tools.format_read_tool_result(
        "get_due_cards", {"total_due": 0, "cards": []}
    )

    assert rendered == "Due recall cards: 0 total.\nNo cards are due right now."


def test_unknown_read_tool_is_rejected() -> None:
    with pytest.raises(ValueError):
        read_tools.execute_read_tool("u1", "read_anything")
