"""Read-only chat tools.

Read tools execute immediately and are never stored as pending actions. They
are deterministic entry points for typed views that normal note retrieval does
not cover: open work and the due recall queue.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel

from ...infrastructure.db.recall_repository import get_recall_repository
from ..commitments.services import list_commitments
from ..memory.services import query_tasks_for_user
from ..recall.deck_service import list_cards
from ..recall.scheduling import SystemClock

MAX_READ_ITEMS = 5


class EmptyArgs(BaseModel):
    pass


@dataclass(slots=True)
class ReadToolDefinition:
    name: str
    args_schema: type[BaseModel]
    executor: Callable[[str, BaseModel], dict[str, Any]]


def _task_payload(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": str(task.get("task_id") or ""),
        "description": str(task.get("description") or ""),
        "due_date": task.get("due_date"),
    }


def _exec_get_open_loops(user_id: str, _args: BaseModel) -> dict[str, Any]:
    open_tasks = query_tasks_for_user(user_id, status="open")
    in_progress = query_tasks_for_user(user_id, status="in_progress")
    goals = list_commitments(user_id, status="active")
    return {
        "counts": {
            "open_tasks": len(open_tasks),
            "in_progress_tasks": len(in_progress),
            "active_goals": len(goals),
        },
        "tasks": [_task_payload(task) for task in open_tasks[:MAX_READ_ITEMS]],
        "in_progress": [_task_payload(task) for task in in_progress[:MAX_READ_ITEMS]],
        "goals": [
            {
                "commitment_id": str(goal.get("commitment_id") or ""),
                "text": str(goal.get("text") or ""),
                "progress": goal.get("progress") or 0,
            }
            for goal in goals[:MAX_READ_ITEMS]
        ],
    }


def _exec_get_due_cards(user_id: str, _args: BaseModel) -> dict[str, Any]:
    repo = get_recall_repository()
    clock = SystemClock()
    now = clock.now()
    cards = list_cards(
        user_id,
        repo=repo,
        include_not_due=False,
        status="active",
        clock=clock,
        limit=MAX_READ_ITEMS,
    )
    total_due = repo.query_cards_page(
        user_id,
        status="active",
        due_before=now.isoformat(),
        limit=1,
    )["total"]
    return {
        "total_due": total_due,
        "cards": [
            {
                "card_id": str(card.get("card_id") or ""),
                "deck_id": card.get("deck_id"),
                "question": str(card.get("question") or ""),
                "next_due": card.get("next_due"),
            }
            for card in cards
        ],
    }


READ_TOOL_REGISTRY: dict[str, ReadToolDefinition] = {
    "get_open_loops": ReadToolDefinition(
        name="get_open_loops",
        args_schema=EmptyArgs,
        executor=_exec_get_open_loops,
    ),
    "get_due_cards": ReadToolDefinition(
        name="get_due_cards",
        args_schema=EmptyArgs,
        executor=_exec_get_due_cards,
    ),
}

ENABLED_READ_TOOL_NAMES = {"get_open_loops", "get_due_cards"}


def execute_read_tool(
    user_id: str, tool_name: str, args: dict[str, Any] | None = None
) -> dict[str, Any]:
    if tool_name not in ENABLED_READ_TOOL_NAMES:
        raise ValueError(f"Read tool is disabled: {tool_name}")
    definition = READ_TOOL_REGISTRY.get(tool_name)
    if not definition:
        raise ValueError(f"Unknown read tool: {tool_name}")
    validated_args = definition.args_schema(**(args or {}))
    return definition.executor(user_id, validated_args)


def format_read_tool_result(tool_name: str, result: dict[str, Any]) -> str:
    if tool_name == "get_open_loops":
        counts = result.get("counts") or {}
        lines = [
            (
                "Open loops: "
                f"{counts.get('open_tasks', 0)} open task(s), "
                f"{counts.get('in_progress_tasks', 0)} in progress, "
                f"{counts.get('active_goals', 0)} active goal(s)."
            )
        ]
        tasks = result.get("tasks") or []
        in_progress = result.get("in_progress") or []
        goals = result.get("goals") or []
        if tasks:
            lines.append("Open tasks:")
            lines.extend(
                f"- id={task.get('task_id')}: {task.get('description')}" for task in tasks
            )
        if in_progress:
            lines.append("In-progress tasks:")
            lines.extend(
                f"- id={task.get('task_id')}: {task.get('description')}"
                for task in in_progress
            )
        if goals:
            lines.append("Active goals:")
            lines.extend(
                (
                    f"- id={goal.get('commitment_id')}: {goal.get('text')} "
                    f"({goal.get('progress') or 0}%)"
                )
                for goal in goals
            )
        if not tasks and not in_progress and not goals:
            lines.append("There are no open tasks, in-progress tasks, or active goals.")
        return "\n".join(lines)

    if tool_name == "get_due_cards":
        total_due = int(result.get("total_due") or 0)
        cards = result.get("cards") or []
        lines = [f"Due recall cards: {total_due} total."]
        if not cards:
            return lines[0] + "\nNo cards are due right now."
        lines.append("Due now:")
        lines.extend(
            f"- id={card.get('card_id')}: {card.get('question')}" for card in cards
        )
        return "\n".join(lines)

    return "No tool results."
