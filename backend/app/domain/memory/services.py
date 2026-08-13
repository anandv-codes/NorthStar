from __future__ import annotations

import re
from typing import Any

from ...infrastructure.db.memory_repository import get_memory_repository
from ..ports import MemoryRepository


def create_extraction_run(
    user_id: str,
    note_id: str,
    model_name: str,
    prompt_version: str,
    status: str = "completed",
    error_message: str | None = None,
    repo: MemoryRepository | None = None,
) -> dict[str, Any]:
    repo = repo or get_memory_repository()
    return repo.create_extraction_run(
        user_id=user_id,
        note_id=note_id,
        model_name=model_name,
        prompt_version=prompt_version,
        status=status,
        error_message=error_message,
    )


def insert_tasks(
    user_id: str,
    source_note_id: str,
    extraction_run_id: str | None,
    tasks: list[dict[str, Any]],
    repo: MemoryRepository | None = None,
) -> list[dict[str, Any]]:
    repo = repo or get_memory_repository()
    return repo.insert_tasks(
        user_id=user_id, source_note_id=source_note_id, extraction_run_id=extraction_run_id, tasks=tasks
    )


def insert_facts(
    user_id: str,
    source_note_id: str,
    extraction_run_id: str | None,
    facts: list[dict[str, Any]],
    repo: MemoryRepository | None = None,
) -> list[dict[str, Any]]:
    repo = repo or get_memory_repository()
    return repo.insert_facts(
        user_id=user_id, source_note_id=source_note_id, extraction_run_id=extraction_run_id, facts=facts
    )


def insert_questions(
    user_id: str,
    source_note_id: str,
    extraction_run_id: str | None,
    questions: list[dict[str, Any]],
    repo: MemoryRepository | None = None,
) -> list[dict[str, Any]]:
    repo = repo or get_memory_repository()
    return repo.insert_questions(
        user_id=user_id, source_note_id=source_note_id, extraction_run_id=extraction_run_id, questions=questions
    )


def insert_decisions(
    user_id: str,
    source_note_id: str,
    extraction_run_id: str | None,
    decisions: list[dict[str, Any]],
    repo: MemoryRepository | None = None,
) -> list[dict[str, Any]]:
    repo = repo or get_memory_repository()
    return repo.insert_decisions(
        user_id=user_id, source_note_id=source_note_id, extraction_run_id=extraction_run_id, decisions=decisions
    )


def insert_risks(
    user_id: str,
    source_note_id: str,
    extraction_run_id: str | None,
    risks: list[dict[str, Any]],
    repo: MemoryRepository | None = None,
) -> list[dict[str, Any]]:
    repo = repo or get_memory_repository()
    return repo.insert_risks(
        user_id=user_id, source_note_id=source_note_id, extraction_run_id=extraction_run_id, risks=risks
    )


def insert_concepts(
    user_id: str,
    source_note_id: str,
    extraction_run_id: str | None,
    concepts: list[dict[str, Any]],
    repo: MemoryRepository | None = None,
) -> list[dict[str, Any]]:
    repo = repo or get_memory_repository()
    return repo.insert_concepts(
        user_id=user_id, source_note_id=source_note_id, extraction_run_id=extraction_run_id, concepts=concepts
    )


def upsert_entities(
    user_id: str,
    entities: list[dict[str, Any]],
    repo: MemoryRepository | None = None,
) -> list[dict[str, Any]]:
    repo = repo or get_memory_repository()
    return repo.upsert_entities(user_id=user_id, entities=entities)


def insert_memory_item_entity_links(
    user_id: str,
    source_note_id: str,
    links: list[dict[str, Any]],
    repo: MemoryRepository | None = None,
) -> list[dict[str, Any]]:
    repo = repo or get_memory_repository()
    return repo.insert_memory_item_entity_links(user_id=user_id, source_note_id=source_note_id, links=links)


def query_tasks_for_user(
    user_id: str, status: str | None = None, repo: MemoryRepository | None = None
) -> list[dict[str, Any]]:
    repo = repo or get_memory_repository()
    return repo.query_tasks_for_user(user_id=user_id, status=status)


def query_questions_for_user(
    user_id: str, status: str | None = None, repo: MemoryRepository | None = None
) -> list[dict[str, Any]]:
    repo = repo or get_memory_repository()
    return repo.query_questions_for_user(user_id=user_id, status=status)


def query_risks_for_user(
    user_id: str, status: str | None = None, repo: MemoryRepository | None = None
) -> list[dict[str, Any]]:
    repo = repo or get_memory_repository()
    return repo.query_risks_for_user(user_id=user_id, status=status)


def query_concepts_for_user(
    user_id: str, status: str | None = None, repo: MemoryRepository | None = None
) -> list[dict[str, Any]]:
    repo = repo or get_memory_repository()
    return repo.query_concepts_for_user(user_id=user_id, status=status)


def query_recent_memory_for_user(
    user_id: str, limit: int = 10, repo: MemoryRepository | None = None
) -> dict[str, list[dict[str, Any]]]:
    repo = repo or get_memory_repository()
    return repo.query_recent_memory_for_user(user_id=user_id, limit=limit)


def update_task_item(
    user_id: str, task_id: str, updates: dict[str, Any], repo: MemoryRepository | None = None
) -> dict[str, Any]:
    repo = repo or get_memory_repository()
    return repo.update_task_item(user_id=user_id, task_id=task_id, updates=updates)


def update_question_item(
    user_id: str, question_id: str, updates: dict[str, Any], repo: MemoryRepository | None = None
) -> dict[str, Any]:
    repo = repo or get_memory_repository()
    return repo.update_question_item(user_id=user_id, question_id=question_id, updates=updates)


def update_risk_item(
    user_id: str, risk_id: str, updates: dict[str, Any], repo: MemoryRepository | None = None
) -> dict[str, Any]:
    repo = repo or get_memory_repository()
    return repo.update_risk_item(user_id=user_id, risk_id=risk_id, updates=updates)


def update_concept_item(
    user_id: str, concept_id: str, updates: dict[str, Any], repo: MemoryRepository | None = None
) -> dict[str, Any]:
    repo = repo or get_memory_repository()
    return repo.update_concept_item(user_id=user_id, concept_id=concept_id, updates=updates)


def query_latest_extraction_run_for_note(
    user_id: str, note_id: str, repo: MemoryRepository | None = None
) -> dict[str, Any]:
    repo = repo or get_memory_repository()
    return repo.query_latest_extraction_run_for_note(user_id=user_id, note_id=note_id)


def query_tasks_by_source_note(
    user_id: str, note_id: str, repo: MemoryRepository | None = None
) -> list[dict[str, Any]]:
    repo = repo or get_memory_repository()
    return repo.query_tasks_by_source_note(user_id=user_id, note_id=note_id)


def query_facts_by_source_note(
    user_id: str, note_id: str, repo: MemoryRepository | None = None
) -> list[dict[str, Any]]:
    repo = repo or get_memory_repository()
    return repo.query_facts_by_source_note(user_id=user_id, note_id=note_id)


def query_questions_by_source_note(
    user_id: str, note_id: str, repo: MemoryRepository | None = None
) -> list[dict[str, Any]]:
    repo = repo or get_memory_repository()
    return repo.query_questions_by_source_note(user_id=user_id, note_id=note_id)


def query_decisions_by_source_note(
    user_id: str, note_id: str, repo: MemoryRepository | None = None
) -> list[dict[str, Any]]:
    repo = repo or get_memory_repository()
    return repo.query_decisions_by_source_note(user_id=user_id, note_id=note_id)


def query_risks_by_source_note(
    user_id: str, note_id: str, repo: MemoryRepository | None = None
) -> list[dict[str, Any]]:
    repo = repo or get_memory_repository()
    return repo.query_risks_by_source_note(user_id=user_id, note_id=note_id)


def query_concepts_by_source_note(
    user_id: str, note_id: str, repo: MemoryRepository | None = None
) -> list[dict[str, Any]]:
    repo = repo or get_memory_repository()
    return repo.query_concepts_by_source_note(user_id=user_id, note_id=note_id)


def query_entities_by_source_note(
    user_id: str, note_id: str, repo: MemoryRepository | None = None
) -> list[dict[str, Any]]:
    repo = repo or get_memory_repository()
    return repo.query_entities_by_source_note(user_id=user_id, note_id=note_id)


def apply_deterministic_task_resolution(
    user_id: str,
    raw_text: str,
    source_note_id: str | None = None,
    include_diagnostics: bool = False,
    repo: MemoryRepository | None = None,
) -> list[dict[str, Any]] | dict[str, Any]:
    repo = repo or get_memory_repository()

    def _result(updated_tasks: list[dict[str, Any]], diagnostics: dict[str, Any]):
        if include_diagnostics:
            return {"updated_tasks": updated_tasks, "diagnostics": diagnostics}
        return updated_tasks

    diagnostics: dict[str, Any] = {
        "source_note_id": source_note_id,
        "completion_detected": False,
        "note_tokens": [],
        "note_numbers": [],
        "open_task_count": 0,
        "candidate_matches": [],
        "top_score": None,
        "selected_task_ids": [],
        "selection_blocked_reason": None,
    }

    text = str(raw_text or "").strip()
    if not text:
        diagnostics["selection_blocked_reason"] = "empty_note_text"
        return _result([], diagnostics)

    lower_text = text.lower()
    completion_pattern = r"\b(done|completed|finished|resolved|closed|fixed)\b"
    if not re.search(completion_pattern, lower_text):
        diagnostics["selection_blocked_reason"] = "no_completion_marker"
        return _result([], diagnostics)
    diagnostics["completion_detected"] = True

    open_tasks = repo.query_tasks_for_user(user_id=user_id, status="open")
    diagnostics["open_task_count"] = len(open_tasks)
    if not open_tasks:
        diagnostics["selection_blocked_reason"] = "no_open_tasks"
        return _result([], diagnostics)

    note_tokens = _normalized_tokens(text)
    note_numbers = _number_tokens(text)
    diagnostics["note_tokens"] = sorted(note_tokens)
    diagnostics["note_numbers"] = sorted(note_numbers)
    if not note_tokens:
        diagnostics["selection_blocked_reason"] = "no_meaningful_note_tokens"
        return _result([], diagnostics)

    ranked: list[tuple[int, dict[str, Any]]] = []
    for task in open_tasks:
        description = str(task.get("description") or "")
        task_tokens = _normalized_tokens(description)
        if not task_tokens:
            continue
        if note_numbers and not note_numbers.issubset(_number_tokens(description)):
            continue
        overlap = len(note_tokens.intersection(task_tokens))
        if overlap > 0:
            diagnostics["candidate_matches"].append(
                {
                    "task_id": task.get("task_id"),
                    "source_note_id": task.get("source_note_id"),
                    "description": description,
                    "overlap_score": overlap,
                    "matched_tokens": sorted(note_tokens.intersection(task_tokens)),
                }
            )
            ranked.append((overlap, task))

    if not ranked:
        diagnostics["selection_blocked_reason"] = "no_matching_open_task"
        return _result([], diagnostics)

    ranked.sort(key=lambda item: item[0], reverse=True)
    top_score = ranked[0][0]
    diagnostics["top_score"] = top_score
    best = [task for score, task in ranked if score == top_score]
    diagnostics["selected_task_ids"] = [task.get("task_id") for task in best if task.get("task_id")]

    if top_score < 2 and len(best) != 1:
        diagnostics["selection_blocked_reason"] = "ambiguous_low_confidence_match"
        return _result([], diagnostics)

    updated: list[dict[str, Any]] = []
    for task in best:
        row = repo.update_task_item(
            user_id=user_id,
            task_id=task["task_id"],
            updates={"status": "completed"},
        )
        if row:
            updated.append(row)
    return _result(updated, diagnostics)


def _number_tokens(text: str) -> set[str]:
    return set(re.findall(r"\d+", text.lower()))


def _normalized_tokens(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    stop_words = {
        "a",
        "an",
        "and",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "to",
        "was",
        "were",
        "with",
        "pending",
        "done",
        "complete",
        "completed",
    }
    return {token for token in tokens if token not in stop_words}
