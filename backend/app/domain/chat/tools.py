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
from ..memory.services import (
    insert_concepts,
    insert_questions,
    insert_risks,
    insert_tasks,
    query_concepts_for_user,
    query_questions_for_user,
    query_risks_for_user,
    query_tasks_for_user,
    update_concept_item,
    update_question_item,
    update_risk_item,
    update_task_item,
)


def _truncate(text: str, limit: int = MAX_ITEM_TEXT_LENGTH_FOR_TOOL_CONTEXT) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def _create_synthetic_anchor_note(user_id: str, tool_name: str, source_text: str) -> str:
    """Create a minimal 'note' row so chat-created items satisfy the tasks/questions/
    risks/concepts tables' NOT NULL source_note_id FK, without running it through the
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
    """Mark an existing OPEN task as completed. Only use when the user clearly refers
    to one task from the 'Open tasks' list provided in context, by its id. Never invent
    an id that isn't listed."""

    task_id: str = Field(..., description="The exact task_id copied from the Open tasks list.")


class CreateQuestionArgs(BaseModel):
    """Record a brand-new open question. Use only when the user is clearly asking to
    log/track a new open question, not when they are asking you something directly."""

    question: str = Field(..., min_length=1, description="The open question to record.")


class AnswerQuestionArgs(BaseModel):
    """Mark an existing OPEN question as answered. Only use when the user clearly refers
    to one question from the 'Open questions' list provided in context, by its id."""

    question_id: str = Field(..., description="The exact question_id copied from the Open questions list.")
    answer: str = Field(..., min_length=1, description="The answer the user gave for this question.")


class CreateRiskArgs(BaseModel):
    """Record a brand-new open risk. Use only when the user is clearly flagging a new
    risk/concern to track."""

    risk: str = Field(..., min_length=1, description="Description of the new risk.")
    severity: str | None = Field(default=None, description="One of: low, medium, high (omit if unstated).")


class ResolveRiskArgs(BaseModel):
    """Mark an existing OPEN risk as resolved. Only use when the user clearly refers to
    one risk from the 'Open risks' list provided in context, by its id."""

    risk_id: str = Field(..., description="The exact risk_id copied from the Open risks list.")


class CreateConceptArgs(BaseModel):
    """Record a brand-new concept the user wants to track learning about. Use only when
    the user is clearly introducing a new concept/topic to learn, not an existing one."""

    concept: str = Field(..., min_length=1, description="Name or short description of the concept.")


class MarkConceptLearnedArgs(BaseModel):
    """Mark an existing OPEN concept as learned. Only use when the user clearly refers to
    one concept from the 'Open concepts' list provided in context, by its id."""

    concept_id: str = Field(..., description="The exact concept_id copied from the Open concepts list.")


@dataclass(slots=True)
class ToolDefinition:
    name: str
    args_schema: type[BaseModel]
    executor: Callable[[str, BaseModel], dict[str, Any]]
    describe: Callable[[BaseModel, dict[str, str]], str]
    confirmed_message: Callable[[BaseModel, dict[str, str]], str]


# Scoped down to tasks for now — question/risk/concept tools stay defined below
# (and in TOOL_REGISTRY) so re-enabling them later is a one-line change here.
ENABLED_TOOL_NAMES = {"create_task", "complete_task"}


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


def _exec_create_risk(user_id: str, args: CreateRiskArgs) -> dict[str, Any]:
    note_id = _create_synthetic_anchor_note(user_id, "create_risk", args.risk)
    rows = insert_risks(
        user_id=user_id,
        source_note_id=note_id,
        extraction_run_id=None,
        risks=[{"risk": args.risk, "severity": args.severity, "status": "open", "created_by": "user"}],
    )
    return rows[0] if rows else {}


def _exec_resolve_risk(user_id: str, args: ResolveRiskArgs) -> dict[str, Any]:
    return update_risk_item(user_id=user_id, risk_id=args.risk_id, updates={"status": "resolved"})


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
    "create_risk": ToolDefinition(
        name="create_risk",
        args_schema=CreateRiskArgs,
        executor=_exec_create_risk,
        describe=lambda args, _lookup: f'record a new open risk: "{args.risk}"',
        confirmed_message=lambda args, _lookup: f'Done — I\'ve recorded the risk "{args.risk}".',
    ),
    "resolve_risk": ToolDefinition(
        name="resolve_risk",
        args_schema=ResolveRiskArgs,
        executor=_exec_resolve_risk,
        describe=lambda args, lookup: f'mark the risk "{lookup.get(args.risk_id, args.risk_id)}" as resolved',
        confirmed_message=lambda args, lookup: (
            f'Done — I\'ve marked "{lookup.get(args.risk_id, args.risk_id)}" as resolved.'
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
    sections = [
        ("Open tasks", query_tasks_for_user(user_id, status="open"), "task_id", "description"),
    ]
    if "create_question" in ENABLED_TOOL_NAMES or "answer_question" in ENABLED_TOOL_NAMES:
        sections.append(("Open questions", query_questions_for_user(user_id, status="open"), "question_id", "question"))
    if "create_risk" in ENABLED_TOOL_NAMES or "resolve_risk" in ENABLED_TOOL_NAMES:
        sections.append(("Open risks", query_risks_for_user(user_id, status="open"), "risk_id", "risk"))
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
