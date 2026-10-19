"""Generate questions for persisted recall candidates (question-first flow).

Only the question is produced here; the answer is generated after the user
accepts a suggestion (see the recall API in PR8). Candidates whose question
fails validation are marked ``rejected`` with the reason recorded.
"""
from __future__ import annotations

from typing import Any

from .card_generation import RecallConfig, generate_question, load_recall_config


def build_context(
    source_note_text: str,
    related_snippets: list[str] | None = None,
    entity_names: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "source_note_text": source_note_text,
        "related_snippets": [snippet for snippet in (related_snippets or []) if snippet],
        "entity_names": [name for name in (entity_names or []) if name],
    }


def generate_questions_for_note(
    user_id: str,
    note_id: str,
    context: dict[str, Any],
    *,
    model: Any,
    repo: Any,
    config: RecallConfig | None = None,
) -> list[dict[str, Any]]:
    """Generate questions for a note's not-yet-questioned (eligible) candidates.

    Used both after processing (when recall is enabled) and when the user
    toggles recall ON for an already-processed note.
    """
    known = [
        row.get("prompt")
        for row in repo.query_candidates(user_id)
        if row.get("prompt")
    ]
    candidates = repo.query_candidates(
        user_id, status="eligible", source_note_id=note_id
    )
    return generate_questions(
        candidates,
        context,
        model=model,
        repo=repo,
        existing_questions=known,
        config=config,
    )


def generate_questions(
    candidates: list[dict[str, Any]],
    context: dict[str, Any],
    *,
    model: Any,
    repo: Any,
    existing_questions: list[str] | None = None,
    config: RecallConfig | None = None,
) -> list[dict[str, Any]]:
    """Generate + validate a question per candidate and persist the decision."""
    config = config or load_recall_config()
    known = list(existing_questions or [])
    results: list[dict[str, Any]] = []

    for candidate in candidates:
        result = generate_question(
            candidate.get("text") or "",
            candidate.get("item_type") or "fact",
            context,
            model,
            known,
            config,
        )
        if result["status"] == "generated":
            known.append(result["question"])
            updates: dict[str, Any] = {
                "prompt": result["question"],
                "status": "suggested",
            }
        else:
            updates = {
                "status": "rejected",
                "rationale": {
                    **(candidate.get("rationale") or {}),
                    "question_reason": result["reason"],
                },
            }

        if candidate.get("candidate_id"):
            repo.update_candidate(candidate["user_id"], candidate["candidate_id"], updates)
        results.append(
            {
                "candidate_id": candidate.get("candidate_id"),
                "status": updates["status"],
                "question": updates.get("prompt"),
                "reason": result["reason"],
            }
        )
    return results
