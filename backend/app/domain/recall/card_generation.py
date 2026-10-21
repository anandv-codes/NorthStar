"""Question/answer card generation with validation and de-duplication.

Flow (product decision): a candidate's **question** is generated first; only a
validated question incurs an **answer** call. The pair is queued for the user,
and accepting it copies both fields onto a card (see ``review_service``).

The LLM is injected as a ``ChatModel`` so generation logic is testable with a
fake. All validation is deterministic and lives here, not in the prompt.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from ...infrastructure.llm.prompt_render import render_prompt_template
from ...infrastructure.llm.prompt_loader import load_prompt
from .text_utils import jaccard_similarity, normalize_text, token_overlap_ratio

PROMPT_VERSION = os.getenv("WORK_MEMORY_PROMPT_VERSION", "phase3-v1")
QUESTION_PROMPT_FILENAME = "03-recall-question_prompt.txt"
ANSWER_PROMPT_FILENAME = "04-recall-answer_prompt.txt"

GENERIC_QUESTIONS = {
    "what does this note say",
    "what is this about",
    "what does the note say",
    "summarize this",
    "what is this note about",
}


@dataclass(frozen=True)
class RecallConfig:
    max_question_chars: int = 240
    max_answer_chars: int = 600
    min_answer_overlap: float = 0.3
    duplicate_threshold: float = 0.9
    max_attempts: int = 2


def load_recall_config() -> RecallConfig:
    return RecallConfig(
        max_question_chars=int(os.getenv("RECALL_MAX_QUESTION_CHARS", "240")),
        max_answer_chars=int(os.getenv("RECALL_MAX_ANSWER_CHARS", "600")),
        min_answer_overlap=float(os.getenv("RECALL_MIN_ANSWER_OVERLAP", "0.3")),
        duplicate_threshold=float(os.getenv("RECALL_DUPLICATE_THRESHOLD", "0.9")),
        max_attempts=int(os.getenv("RECALL_GENERATION_ATTEMPTS", "2")),
    )


# ---------------------------------------------------------------------------
# Prompt rendering
# ---------------------------------------------------------------------------

def build_question_prompt(
    candidate_text: str,
    item_type: str,
    context: dict[str, Any],
    stricter: bool = False,
) -> str:
    template = load_prompt(PROMPT_VERSION, QUESTION_PROMPT_FILENAME)
    rendered = render_prompt_template(
        template,
        {
            "item_type": item_type,
            "candidate_text": candidate_text,
            "source_note_text": _as_text(context.get("source_note_text")),
            "related_snippets": _format_snippets(context.get("related_snippets")),
            "entity_names": _format_names(context.get("entity_names")),
        },
    )
    if stricter:
        rendered += (
            "\n\nYour previous question was rejected. Ask a more specific, "
            "single-idea question grounded only in the supplied notes."
        )
    return rendered


def build_answer_prompt(question: str, context: dict[str, Any]) -> str:
    template = load_prompt(PROMPT_VERSION, ANSWER_PROMPT_FILENAME)
    return render_prompt_template(
        template,
        {
            "question": question,
            "candidate_text": _as_text(context.get("candidate_text")),
            "source_note_text": _as_text(context.get("source_note_text")),
            "related_snippets": _format_snippets(context.get("related_snippets")),
            "entity_names": _format_names(context.get("entity_names")),
        },
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_question(
    question: str,
    existing_questions: list[str] | None = None,
    config: RecallConfig | None = None,
) -> tuple[bool, str | None]:
    config = config or load_recall_config()
    text = str(question or "").strip()
    if not text or not text.endswith("?"):
        return False, "not_a_question"
    if len(text) > config.max_question_chars:
        return False, "question_too_long"
    if normalize_text(text).rstrip("?") in GENERIC_QUESTIONS:
        return False, "generic_question"
    for existing in existing_questions or []:
        if jaccard_similarity(text, existing) >= config.duplicate_threshold:
            return False, "duplicate_question"
    return True, None


def validate_answer(
    answer: str,
    context_text: str,
    config: RecallConfig | None = None,
) -> tuple[bool, str | None]:
    config = config or load_recall_config()
    text = str(answer or "").strip()
    if not text:
        return False, "empty_answer"
    if len(text) > config.max_answer_chars:
        return False, "answer_too_long"
    if token_overlap_ratio(text, context_text) < config.min_answer_overlap:
        return False, "answer_not_grounded"
    return True, None


def validate_answer_edit(
    answer: str,
    config: RecallConfig | None = None,
) -> tuple[bool, str | None]:
    """Validate a user-edited answer without requiring overlap with context."""
    config = config or load_recall_config()
    text = str(answer or "").strip()
    if not text:
        return False, "empty_answer"
    if len(text) > config.max_answer_chars:
        return False, "answer_too_long"
    return True, None


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def generate_question(
    candidate_text: str,
    item_type: str,
    context: dict[str, Any],
    model: Any,
    existing_questions: list[str] | None = None,
    config: RecallConfig | None = None,
) -> dict[str, Any]:
    """Generate a validated question, retrying once, else return rejected status."""
    config = config or load_recall_config()
    last_reason = "generation_failed"
    for attempt in range(max(1, config.max_attempts)):
        raw = model.generate(
            build_question_prompt(candidate_text, item_type, context, stricter=attempt > 0)
        )
        question = _extract_field(raw, "question")
        ok, reason = validate_question(question, existing_questions, config)
        if ok:
            return {"question": question.strip(), "status": "generated", "reason": None}
        last_reason = reason or last_reason
    return {"question": None, "status": "rejected", "reason": last_reason}


def generate_answer(
    question: str,
    context: dict[str, Any],
    model: Any,
    config: RecallConfig | None = None,
) -> dict[str, Any]:
    config = config or load_recall_config()
    context_text = " ".join(
        [
            _as_text(context.get("candidate_text")),
            _as_text(context.get("source_note_text")),
            " ".join(context.get("related_snippets") or []),
        ]
    )
    last_reason = "generation_failed"
    for attempt in range(max(1, config.max_attempts)):
        raw = model.generate(build_answer_prompt(question, context))
        answer = _extract_field(raw, "answer")
        ok, reason = validate_answer(answer, context_text, config)
        if ok:
            return {"answer": answer.strip(), "status": "generated", "reason": None}
        last_reason = reason or last_reason
    return {"answer": None, "status": "rejected", "reason": last_reason}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_field(raw: str, field: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and isinstance(parsed.get(field), str):
            return parsed[field]
    except (json.JSONDecodeError, TypeError):
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict) and isinstance(parsed.get(field), str):
                return parsed[field]
        except (json.JSONDecodeError, TypeError):
            pass
    # Fall back to the raw text (models sometimes ignore the JSON wrapper).
    return text


def _as_text(value: Any) -> str:
    return str(value).strip() if value else ""


def _format_snippets(snippets: Any) -> str:
    if not snippets:
        return "None."
    return "\n".join(f"- {_as_text(snippet)}" for snippet in snippets)


def _format_names(names: Any) -> str:
    if not names:
        return "None."
    return ", ".join(str(name) for name in names)
