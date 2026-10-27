"""Extraction v2 helpers: scoring, due dates, metadata projection, commitments.

Pure functions over the raw extraction dict so they are easy to unit test and
reuse from the worker without importing any infrastructure. The raw Gemini
response is intentionally kept as ``notes.metadata`` JSON (per final.md);
only high-value items are additionally normalized into typed tables.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

METADATA_SCHEMA_VERSION = 2

_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")

# Fallback when the model omits both importance and confidence for an item.
DEFAULT_ITEM_SCORE = 0.5
DEFAULT_IMPORTANCE_DELTA = 0.1
MAX_ENTITY_IMPORTANCE = 1.0


def clamp_score(value: Any, default: float | None = None) -> float | None:
    """Coerce a value into [0, 1], returning ``default`` when unusable."""
    if value is None or isinstance(value, bool):
        return default
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, numeric))


def normalize_due_date(value: Any) -> str | None:
    """Return an ISO ``YYYY-MM-DD`` date or ``None`` for absent/invalid input."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    match = _DATE_RE.search(str(value))
    if not match:
        return None
    candidate = match.group(1)
    try:
        datetime.strptime(candidate, "%Y-%m-%d")
    except ValueError:
        return None
    return candidate


def item_importance(item: dict[str, Any]) -> float:
    """Importance for a task/fact/concept, falling back to confidence."""
    for key in ("importance", "confidence"):
        score = clamp_score(item.get(key))
        if score is not None:
            return score
    return DEFAULT_ITEM_SCORE


def item_durability(item: dict[str, Any]) -> float:
    score = clamp_score(item.get("durability"))
    return score if score is not None else DEFAULT_ITEM_SCORE


def _scored_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        **item,
        "importance": item_importance(item),
        "durability": item_durability(item),
    }


def build_note_metadata(extraction: dict[str, Any]) -> dict[str, Any]:
    """Project a raw extraction into the JSONB stored on ``notes.metadata``.

    Scores are normalized so downstream recall scoring can read them without
    re-deriving defaults.
    """
    return {
        "schema_version": METADATA_SCHEMA_VERSION,
        "summary": extraction.get("summary", ""),
        "tasks": [_scored_item(task) for task in extraction.get("tasks", [])],
        "facts": [_scored_item(fact) for fact in extraction.get("facts", [])],
        "concepts": [_scored_item(concept) for concept in extraction.get("concepts", [])],
        "questions": list(extraction.get("questions", [])),
        "decisions": list(extraction.get("decisions", [])),
        "entities": list(extraction.get("entities", [])),
        "commitment_contributions": list(
            extraction.get("commitment_contributions", [])
        ),
    }


def commitment_rows(
    extraction: dict[str, Any],
    user_id: str,
    source_note_id: str,
) -> list[dict[str, Any]]:
    """Normalize extracted commitments into rows ready for the ``commitments`` table."""
    rows: list[dict[str, Any]] = []
    for commitment in extraction.get("commitments", []) or []:
        title = str(commitment.get("title") or "").strip()
        if not title:
            continue
        rows.append(
            {
                "user_id": user_id,
                "source_note_id": source_note_id,
                "title": title,
                "due_date": normalize_due_date(commitment.get("due_date")),
                "confidence": clamp_score(commitment.get("confidence")),
                "status": "pending",
            }
        )
    return rows


def task_rows_with_scoring(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add normalized due_date/importance/durability to extracted tasks."""
    rows = []
    for task in tasks or []:
        rows.append(
            {
                **task,
                "due_date": normalize_due_date(task.get("due_date")),
                "importance": item_importance(task),
                "durability": item_durability(task),
            }
        )
    return rows


def entity_importance_delta(names: list[str]) -> float:
    """Per-mention importance bump for recurring entities, capped at 1.0."""
    unique = {str(name).strip().lower() for name in names if str(name).strip()}
    if not unique:
        return 0.0
    return min(MAX_ENTITY_IMPORTANCE, DEFAULT_IMPORTANCE_DELTA * len(unique))
