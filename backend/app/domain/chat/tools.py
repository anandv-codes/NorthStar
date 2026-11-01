"""Chat tool definitions: schemas the LLM can call, and the executors that
apply the corresponding work-memory DB change once the user confirms.

Every tool here mutates data, so none of these are called directly from the
tool resolver — a proposal is stored as a pending action and only executed
after an explicit "yes" from the user (see ``domain/chat/services.py``).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from pydantic import BaseModel, Field

from ...infrastructure.db.supabase_client import put_note_item
from ...infrastructure.llm.llm_config import (
    MAX_ITEM_TEXT_LENGTH_FOR_TOOL_CONTEXT,
    MAX_OPEN_ITEMS_FOR_TOOL_CONTEXT,
)
from ..commitments.services import list_commitments, update_commitment
from ..memory.services import (
    insert_concepts,
    insert_questions,
    insert_tasks,
    query_concepts_for_user,
    query_questions_for_user,
    query_tasks_for_user,
    update_concept_item,
    update_question_item,
    update_task_item,
)


def _truncate(text: str, limit: int = MAX_ITEM_TEXT_LENGTH_FOR_TOOL_CONTEXT) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def _create_synthetic_anchor_note(user_id: str, tool_name: str, source_text: str) -> str:
    """Create a minimal 'note' row so chat-created items satisfy the tasks/questions/
    concepts tables' NOT NULL source_note_id FK, without running it through the
    note extraction pipeline (status is already 'processed', no SQS job is sent)."""
    note_id = str(uuid.uuid4())
    put_note_item(
        {
            "note_id": note_id,
            "user_id": user_id,
            "status": "processed",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "raw_text": f"[chat] {source_text}",
            "metadata": {"origin": "chat_tool_action", "tool_name": tool_name},
        }
    )
    return note_id


# ---------------------------------------------------------------------------
# Tool argument schemas. Docstrings double as the tool description the model
# sees, so they must state precisely when (and when not) to use the tool.
# ---------------------------------------------------------------------------


class CreateTaskArgs(BaseModel):
    """Create a brand-new open task. Use only when the user is clearly asking to
    add/create/remember a new to-do item. Never use this to close an existing task."""

    description: str = Field(..., min_length=1, description="Clear, actionable description of the new task.")


class CompleteTaskArgs(BaseModel):
    """Mark an existing OPEN or IN-PROGRESS task as completed. Only use when the user
    clearly refers to one task from the task lists provided in context, by its id.
    Never invent an id that isn't listed."""

    task_id: str = Field(..., description="The exact task_id copied from the task lists.")


class CreateQuestionArgs(BaseModel):
    """Record a brand-new open question. Use only when the user is clearly asking to
    log/track a new open question, not when they are asking you something directly."""

    question: str = Field(..., min_length=1, description="The open question to record.")


class AnswerQuestionArgs(BaseModel):
    """Mark an existing OPEN question as answered. Only use when the user clearly refers
    to one question from the 'Open questions' list provided in context, by its id."""

    question_id: str = Field(..., description="The exact question_id copied from the Open questions list.")
    answer: str = Field(..., min_length=1, description="The answer the user gave for this question.")


class CreateConceptArgs(BaseModel):
    """Record a brand-new concept the user wants to track learning about. Use only when
    the user is clearly introducing a new concept/topic to learn, not an existing one."""

    concept: str = Field(..., min_length=1, description="Name or short description of the concept.")


class MarkConceptLearnedArgs(BaseModel):
    """Mark an existing OPEN concept as learned. Only use when the user clearly refers to
    one concept from the 'Open concepts' list provided in context, by its id."""

    concept_id: str = Field(..., description="The exact concept_id copied from the Open concepts list.")


class StartTaskArgs(BaseModel):
    """Mark an existing OPEN task as in progress. Only use when the user clearly refers
    to one task from the task lists provided in context, by its id."""

    task_id: str = Field(..., description="The exact task_id copied from the task lists.")


class ReopenTaskArgs(BaseModel):
    """Reopen an existing COMPLETED or ARCHIVED task. Only use when the user clearly
    refers to one task from the completed/archived lists provided in context."""

    task_id: str = Field(..., description="The exact task_id copied from the task lists.")


class ArchiveTaskArgs(BaseModel):
    """Archive an existing task. Only use when the user clearly refers to one task from
    the task lists provided in context, by its id."""

    task_id: str = Field(..., description="The exact task_id copied from the task lists.")


class UpdateCommitmentProgressArgs(BaseModel):
    """Set the progress percentage on an existing ACTIVE long-term goal. Only use when
    the user clearly refers to one goal from the active goals list, by its id."""

    commitment_id: str = Field(
        ..., description="The exact commitment_id copied from the Active goals list."
    )
    progress: int = Field(
        ..., ge=0, le=100, description="Progress percentage from 0 to 100."
    )


@dataclass(slots=True)
class ToolDefinition:
    name: str
    args_schema: type[BaseModel]
    executor: Callable[[str, BaseModel], dict[str, Any]]
    describe: Callable[[BaseModel, dict[str, str]], str]
    confirmed_message: Callable[[BaseModel, dict[str, str]], str]


# Question/concept tools stay defined below (and in TOOL_REGISTRY) but remain
# disabled until typed question/concept reads and writes are explicitly scoped.
ENABLED_TOOL_NAMES = {
    "create_task",
    "complete_task",
    "start_task",
    "reopen_task",
    "archive_task",
    "update_commitment_progress",
}


def _exec_create_task(user_id: str, args: CreateTaskArgs) -> dict[str, Any]:
    note_id = _create_synthetic_anchor_note(user_id, "create_task", args.description)
    rows = insert_tasks(
        user_id=user_id,
        source_note_id=note_id,
        extraction_run_id=None,
        tasks=[{"description": args.description, "status": "open", "created_by": "user"}],
    )
    return rows[0] if rows else {}


def _exec_complete_task(user_id: str, args: CompleteTaskArgs) -> dict[str, Any]:
    return update_task_item(user_id=user_id, task_id=args.task_id, updates={"status": "completed"})


def _exec_start_task(user_id: str, args: StartTaskArgs) -> dict[str, Any]:
    return update_task_item(
        user_id=user_id,
        task_id=args.task_id,
        updates={"status": "in_progress", "completed_at": None},
    )


def _exec_reopen_task(user_id: str, args: ReopenTaskArgs) -> dict[str, Any]:
    return update_task_item(
        user_id=user_id,
        task_id=args.task_id,
        updates={"status": "open", "completed_at": None},
    )


def _exec_archive_task(user_id: str, args: ArchiveTaskArgs) -> dict[str, Any]:
    return update_task_item(
        user_id=user_id,
        task_id=args.task_id,
        updates={"status": "archived"},
    )


def _exec_update_commitment_progress(
    user_id: str, args: UpdateCommitmentProgressArgs
) -> dict[str, Any]:
    return update_commitment(
        user_id=user_id,
        commitment_id=args.commitment_id,
        updates={"progress": args.progress},
    )


def _exec_create_question(user_id: str, args: CreateQuestionArgs) -> dict[str, Any]:
    note_id = _create_synthetic_anchor_note(user_id, "create_question", args.question)
    rows = insert_questions(
        user_id=user_id,
        source_note_id=note_id,
        extraction_run_id=None,
        questions=[{"question": args.question, "status": "open", "created_by": "user"}],
    )
    return rows[0] if rows else {}


def _exec_answer_question(user_id: str, args: AnswerQuestionArgs) -> dict[str, Any]:
    return update_question_item(
        user_id=user_id,
        question_id=args.question_id,
        updates={"status": "answered", "answer": args.answer},
    )


def _exec_create_concept(user_id: str, args: CreateConceptArgs) -> dict[str, Any]:
    note_id = _create_synthetic_anchor_note(user_id, "create_concept", args.concept)
    rows = insert_concepts(
        user_id=user_id,
        source_note_id=note_id,
        extraction_run_id=None,
        concepts=[{"concept": args.concept, "status": "open", "created_by": "user"}],
    )
    return rows[0] if rows else {}


def _exec_mark_concept_learned(user_id: str, args: MarkConceptLearnedArgs) -> dict[str, Any]:
    return update_concept_item(user_id=user_id, concept_id=args.concept_id, updates={"status": "learned"})


TOOL_REGISTRY: dict[str, ToolDefinition] = {
    "create_task": ToolDefinition(
        name="create_task",
        args_schema=CreateTaskArgs,
        executor=_exec_create_task,
        describe=lambda args, _lookup: f'create a new task: "{args.description}"',
        confirmed_message=lambda args, _lookup: f'Done — I\'ve created the task "{args.description}".',
    ),
    "complete_task": ToolDefinition(
        name="complete_task",
        args_schema=CompleteTaskArgs,
        executor=_exec_complete_task,
        describe=lambda args, lookup: f'mark the task "{lookup.get(args.task_id, args.task_id)}" as completed',
        confirmed_message=lambda args, lookup: (
            f'Done — I\'ve marked "{lookup.get(args.task_id, args.task_id)}" as completed.'
        ),
    ),
    "start_task": ToolDefinition(
        name="start_task",
        args_schema=StartTaskArgs,
        executor=_exec_start_task,
        describe=lambda args, lookup: (
            f'mark the task "{lookup.get(args.task_id, args.task_id)}" as in progress'
        ),
        confirmed_message=lambda args, lookup: (
            f'Done — I\'ve marked "{lookup.get(args.task_id, args.task_id)}" as in progress.'
        ),
    ),
    "reopen_task": ToolDefinition(
        name="reopen_task",
        args_schema=ReopenTaskArgs,
        executor=_exec_reopen_task,
        describe=lambda args, lookup: f'reopen the task "{lookup.get(args.task_id, args.task_id)}"',
        confirmed_message=lambda args, lookup: (
            f'Done — I\'ve reopened "{lookup.get(args.task_id, args.task_id)}".'
        ),
    ),
    "archive_task": ToolDefinition(
        name="archive_task",
        args_schema=ArchiveTaskArgs,
        executor=_exec_archive_task,
        describe=lambda args, lookup: f'archive the task "{lookup.get(args.task_id, args.task_id)}"',
        confirmed_message=lambda args, lookup: (
            f'Done — I\'ve archived "{lookup.get(args.task_id, args.task_id)}".'
        ),
    ),
    "update_commitment_progress": ToolDefinition(
        name="update_commitment_progress",
        args_schema=UpdateCommitmentProgressArgs,
        executor=_exec_update_commitment_progress,
        describe=lambda args, lookup: (
            f'set the goal "{lookup.get(args.commitment_id, args.commitment_id)}" '
            f'to {args.progress}%'
        ),
        confirmed_message=lambda args, lookup: (
            f'Done — I\'ve set "{lookup.get(args.commitment_id, args.commitment_id)}" '
            f'to {args.progress}%.'
        ),
    ),
    "create_question": ToolDefinition(
        name="create_question",
        args_schema=CreateQuestionArgs,
        executor=_exec_create_question,
        describe=lambda args, _lookup: f'record a new open question: "{args.question}"',
        confirmed_message=lambda args, _lookup: f'Done — I\'ve recorded the question "{args.question}".',
    ),
    "answer_question": ToolDefinition(
        name="answer_question",
        args_schema=AnswerQuestionArgs,
        executor=_exec_answer_question,
        describe=lambda args, lookup: (
            f'mark the question "{lookup.get(args.question_id, args.question_id)}" as answered: "{args.answer}"'
        ),
        confirmed_message=lambda args, lookup: (
            f'Done — I\'ve marked "{lookup.get(args.question_id, args.question_id)}" as answered.'
        ),
    ),
    "create_concept": ToolDefinition(
        name="create_concept",
        args_schema=CreateConceptArgs,
        executor=_exec_create_concept,
        describe=lambda args, _lookup: f'record a new concept to learn: "{args.concept}"',
        confirmed_message=lambda args, _lookup: f'Done — I\'ve recorded the concept "{args.concept}".',
    ),
    "mark_concept_learned": ToolDefinition(
        name="mark_concept_learned",
        args_schema=MarkConceptLearnedArgs,
        executor=_exec_mark_concept_learned,
        describe=lambda args, lookup: (
            f'mark the concept "{lookup.get(args.concept_id, args.concept_id)}" as learned'
        ),
        confirmed_message=lambda args, lookup: (
            f'Done — I\'ve marked "{lookup.get(args.concept_id, args.concept_id)}" as learned.'
        ),
    ),
}


def build_tool_context(user_id: str) -> tuple[str, dict[str, str]]:
    """Return (context_text_for_llm_prompt, item_id -> truncated_text lookup)."""
    item_lookup: dict[str, str] = {}
    task_tools = {"create_task", "complete_task", "start_task", "archive_task"}
    sections = []
    if task_tools & ENABLED_TOOL_NAMES:
        sections.append(
            ("Open tasks", query_tasks_for_user(user_id, status="open"), "task_id", "description")
        )
        sections.append(
            (
                "In-progress tasks",
                query_tasks_for_user(user_id, status="in_progress"),
                "task_id",
                "description",
            )
        )
    if "reopen_task" in ENABLED_TOOL_NAMES:
        sections.append(
            (
                "Completed tasks",
                query_tasks_for_user(user_id, status="completed"),
                "task_id",
                "description",
            )
        )
        sections.append(
            (
                "Archived tasks",
                query_tasks_for_user(user_id, status="archived"),
                "task_id",
                "description",
            )
        )
    if "update_commitment_progress" in ENABLED_TOOL_NAMES:
        goals = [
            {**goal, "goal_label": f"{goal.get('text') or ''} ({goal.get('progress') or 0}%)"}
            for goal in list_commitments(user_id, status="active")
        ]
        sections.append(("Active goals", goals, "commitment_id", "goal_label"))
    if "create_question" in ENABLED_TOOL_NAMES or "answer_question" in ENABLED_TOOL_NAMES:
        sections.append(("Open questions", query_questions_for_user(user_id, status="open"), "question_id", "question"))
    if "create_concept" in ENABLED_TOOL_NAMES or "mark_concept_learned" in ENABLED_TOOL_NAMES:
        sections.append(("Open concepts", query_concepts_for_user(user_id, status="open"), "concept_id", "concept"))

    lines: list[str] = []
    for label, items, id_key, text_key in sections:
        lines.append(f"{label}:")
        limited = items[:MAX_OPEN_ITEMS_FOR_TOOL_CONTEXT]
        if not limited:
            lines.append("  (none)")
        for item in limited:
            item_id = str(item.get(id_key) or "")
            text = _truncate(str(item.get(text_key) or ""))
            if item_id:
                item_lookup[item_id] = text
            lines.append(f"  - id={item_id}: {text}")
        lines.append("")

    return "\n".join(lines).strip(), item_lookup
