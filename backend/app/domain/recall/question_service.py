"""Generate questions for persisted recall candidates.

Only the question is produced up front: the answer is generated on demand,
either when the user reveals it during review or when they accept the
suggestion into their deck. That keeps note processing cheap (no second LLM
call per candidate) and avoids paying for answers the user never looks at.
"""
from __future__ import annotations

from typing import Any

from .card_generation import RecallConfig, generate_answer, generate_question, load_recall_config


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
    """Generate + validate a question per candidate and persist the decision.

    Answers stay empty (``None``) until the user reveals or accepts them; see
    :func:`generate_answer_for_candidate`.
    """
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
                "answer": None,
                "status": "suggested",
            }
        else:
            rationale = {
                **(candidate.get("rationale") or {}),
                "question_reason": result["reason"],
            }
            updates = {
                "status": "rejected",
                "prompt": result.get("question"),
                "answer": None,
                "rationale": rationale,
            }

        if candidate.get("candidate_id"):
            repo.update_candidate(candidate["user_id"], candidate["candidate_id"], updates)
        results.append(
            {
                "candidate_id": candidate.get("candidate_id"),
                "status": updates["status"],
                "question": updates.get("prompt"),
                "answer": updates.get("answer"),
                "reason": result["reason"],
            }
        )
    return results


def generate_answer_for_candidate(
    user_id: str,
    candidate_id: str,
    *,
    model: Any,
    repo: Any,
    context: dict[str, Any] | None = None,
    config: RecallConfig | None = None,
) -> dict[str, Any]:
    """Generate and persist an answer for one candidate (idempotent).

    Called when the user reveals an answer or accepts a suggestion. Raises
    ``LookupError`` when the candidate does not exist and ``ValueError`` when it
    has no question or the answer fails grounding validation.
    """
    config = config or load_recall_config()
    candidate = repo.get_candidate(user_id, candidate_id)
    if candidate is None:
        raise LookupError("candidate_not_found")

    question = (candidate.get("prompt") or "").strip()
    if not question:
        raise ValueError("candidate_has_no_question")

    existing = (candidate.get("answer") or "").strip()
    if existing:
        return candidate

    answer_context = {
        **(context or build_context("")),
        "candidate_text": candidate.get("text") or "",
    }
    result = generate_answer(question, answer_context, model, config)
    if result["status"] != "generated":
        reason = result.get("reason") or "unknown"
        raise ValueError(f"answer_generation_failed:{reason}")

    updated = repo.update_candidate(user_id, candidate_id, {"answer": result["answer"]})
    return updated or {**candidate, "answer": result["answer"]}
