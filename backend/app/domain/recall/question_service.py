"""Generate question/answer pairs for persisted recall candidates.

A candidate's question and answer are produced together in one LLM call inside
the asynchronous note worker, and both are persisted at once. A suggestion is
therefore only visible with its answer, and revealing a card is a cache hit in
the common case. If the answer fails validation while the question passes, the
question is kept and the answer is generated on demand (reveal/accept).
"""
from __future__ import annotations

from typing import Any

from .card_generation import (
    RecallConfig,
    generate_answer,
    generate_question_with_answer,
    load_recall_config,
)


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
    """Generate a validated question+answer pair per candidate and persist it.

    The write is conditional on the candidate still being ``eligible`` so a
    duplicate worker delivery (or a synchronous reveal that won the candidate)
    cannot overwrite a pair that was already written. If the question is valid
    but the answer is not, the question is kept with ``answer=None`` and the
    answer is regenerated on reveal/accept.
    """
    config = config or load_recall_config()
    known = list(existing_questions or [])
    results: list[dict[str, Any]] = []

    for candidate in candidates:
        result = generate_question_with_answer(
            candidate.get("text") or "",
            candidate.get("item_type") or "fact",
            context,
            model,
            known,
            config,
        )

        if result["status"] in ("generated", "generated_without_answer"):
            updates: dict[str, Any] = {
                "prompt": result["question"],
                "answer": result.get("answer"),
                "status": "suggested",
            }
            if result["status"] == "generated_without_answer":
                updates["rationale"] = {
                    **(candidate.get("rationale") or {}),
                    "answer_reason": result["reason"],
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
            updated = repo.update_candidate_if_status(
                candidate["user_id"],
                candidate["candidate_id"],
                "eligible",
                updates,
            )
            if not updated:
                # Another worker/request already decided this candidate;
                # do not report a write we did not make.
                results.append(
                    {
                        "candidate_id": candidate.get("candidate_id"),
                        "status": "skipped",
                        "question": None,
                        "answer": None,
                        "reason": "candidate_already_decided",
                    }
                )
                continue
        if result["status"] in ("generated", "generated_without_answer"):
            # Only reserve the question for in-note dedupe after it is actually
            # persisted; a skipped write belongs to another writer.
            known.append(result["question"])
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
    candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate and persist an answer for one candidate (idempotent).

    Called when the user reveals an answer or accepts a suggestion. Raises
    ``LookupError`` when the candidate does not exist and ``ValueError`` when it
    has no question or the answer fails grounding validation. Callers that
    already hold the row can pass ``candidate`` to skip a read.
    """
    config = config or load_recall_config()
    candidate = candidate or repo.get_candidate(user_id, candidate_id)
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
