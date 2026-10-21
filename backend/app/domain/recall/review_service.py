"""Review service: candidate decisions and card review.

Flow: a ``suggested`` candidate is accepted -> its question/answer pair is
copied to a scheduled card. Answers are generated on demand: if the candidate
has no stored answer, acceptance generates one when a model is supplied.
Reviews grade the card and persist both the new scheduling state and an
immutable history entry.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .card_generation import RecallConfig, load_recall_config, validate_answer_edit, validate_question
from .deck_service import ensure_default_deck, get_active_deck
from .question_service import generate_answer_for_candidate
from .scheduling import AnkiScheduler, SystemClock, initial_card_state, load_scheduler_config


def list_suggestions(user_id: str, *, repo: Any, limit: int = 50) -> list[dict[str, Any]]:
    """Candidates awaiting a user decision, highest score first."""
    return repo.query_candidates(user_id, status="suggested", limit=limit)


def due_cards(
    user_id: str, *, repo: Any, clock: Any | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    now = (clock or SystemClock()).now()
    return repo.query_cards(user_id, status="active", due_before=now.isoformat(), limit=limit)


def accept_candidate(
    user_id: str,
    candidate_id: str,
    *,
    repo: Any,
    model: Any | None = None,
    context: dict[str, Any] | None = None,
    recall_config: RecallConfig | None = None,
    now: datetime | None = None,
    deck_id: str | None = None,
) -> dict[str, Any]:
    """Copy the question/answer into a scheduled card and mark the candidate accepted.

    When the candidate has no answer yet, one is generated on acceptance
    (``model`` is required in that case).
    """
    now = now or SystemClock().now()

    candidate = repo.get_candidate(user_id, candidate_id)
    if candidate is None:
        raise LookupError("candidate_not_found")
    if candidate.get("status") == "carded":
        raise ValueError("candidate_already_carded")

    question = (candidate.get("prompt") or "").strip()
    if not question:
        raise ValueError("candidate_has_no_question")
    answer = (candidate.get("answer") or "").strip()
    if not answer:
        if model is None:
            raise ValueError("candidate_has_no_answer")
        candidate = generate_answer_for_candidate(
            user_id,
            candidate_id,
            model=model,
            repo=repo,
            context=context,
            config=recall_config,
        )
        answer = (candidate.get("answer") or "").strip()
        if not answer:
            raise ValueError("candidate_has_no_answer")

    if deck_id is not None:
        get_active_deck(user_id, deck_id, repo=repo)
    resolved_deck_id = deck_id or candidate.get("deck_id")
    if resolved_deck_id:
        deck = repo.get_deck(user_id, resolved_deck_id)
        if deck is None or deck.get("archived_at"):
            resolved_deck_id = None
    if not resolved_deck_id:
        resolved_deck_id = ensure_default_deck(user_id, repo=repo, now=now)["deck_id"]

    state = initial_card_state(now=now)
    card = repo.create_card(
        user_id,
        {
            "candidate_id": candidate_id,
            "deck_id": resolved_deck_id,
            "question": question,
            "answer": answer,
            "source_note_ids": [candidate["source_note_id"]] if candidate.get("source_note_id") else [],
            "status": "active",
            **{k: v for k, v in state.items() if v is not None},
            "next_due": now.isoformat(),
        },
    )
    updated = repo.update_candidate(
        user_id,
        candidate_id,
        {
            "status": "carded",
            "deck_id": resolved_deck_id,
            "decided_at": now.isoformat(),
        },
    )
    return {"status": "carded", "card": card, "candidate": updated or candidate}


def update_suggestion(
    user_id: str,
    candidate_id: str,
    *,
    repo: Any,
    question: str | None = None,
    answer: str | None = None,
    deck_id: str | None = None,
    recall_config: RecallConfig | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Edit the question/answer of a suggestion that has not been decided."""
    recall_config = recall_config or load_recall_config()
    now = now or SystemClock().now()

    candidate = repo.get_candidate(user_id, candidate_id)
    if candidate is None:
        raise LookupError("candidate_not_found")
    if candidate.get("status") != "suggested":
        raise ValueError("candidate_not_editable")
    if question is None and answer is None and deck_id is None:
        raise ValueError("no_fields_to_update")

    updates: dict[str, Any] = {}
    if question is not None:
        normalized_question = str(question).strip()
        ok, reason = validate_question(normalized_question, config=recall_config)
        if not ok:
            raise ValueError(f"invalid_question:{reason}")
        updates["prompt"] = normalized_question
    if answer is not None:
        normalized_answer = str(answer).strip()
        ok, reason = validate_answer_edit(normalized_answer, recall_config)
        if not ok:
            raise ValueError(f"invalid_answer:{reason}")
        updates["answer"] = normalized_answer
    if deck_id is not None:
        get_active_deck(user_id, deck_id, repo=repo)
        updates["deck_id"] = deck_id

    updated = repo.update_candidate(user_id, candidate_id, updates)
    return updated or {**candidate, **updates, "updated_at": now.isoformat()}


def reject_candidate(
    user_id: str, candidate_id: str, *, repo: Any, now: datetime | None = None
) -> dict[str, Any]:
    now = now or SystemClock().now()
    candidate = repo.get_candidate(user_id, candidate_id)
    if candidate is None:
        raise LookupError("candidate_not_found")
    updated = repo.update_candidate(
        user_id, candidate_id, {"status": "rejected", "decided_at": now.isoformat()}
    )
    return {"status": "rejected", "candidate": updated or candidate}


def review_card(
    user_id: str,
    card_id: str,
    grade: int,
    *,
    repo: Any,
    scheduler: Any | None = None,
    now: datetime | None = None,
    elapsed_ms: int | None = None,
) -> dict[str, Any]:
    if grade not in (1, 3, 4, 5):
        raise ValueError("invalid_grade")
    now = now or SystemClock().now()
    scheduler = scheduler or AnkiScheduler(load_scheduler_config())

    card = repo.get_card(user_id, card_id)
    if card is None:
        raise LookupError("card_not_found")

    updates = scheduler.schedule(card, grade, now)
    previous_interval = updates.pop("previous_interval", None)
    previous_easiness = updates.pop("previous_easiness", None)

    updated = repo.update_card(user_id, card_id, updates)
    history = repo.insert_review_history(
        user_id,
        {
            "card_id": card_id,
            "grade": grade,
            "reviewed_at": now.isoformat(),
            "previous_interval": previous_interval,
            "new_interval": updates.get("interval"),
            "previous_easiness": previous_easiness,
            "new_easiness": updates.get("easiness"),
            "elapsed_ms": elapsed_ms,
        },
    )
    return {"card": updated, "history": history, "scheduled": updates}


def accept_candidates(
    user_id: str,
    candidate_ids: list[str],
    *,
    repo: Any,
    model: Any | None = None,
    contexts: dict[str, dict[str, Any]] | None = None,
    recall_config: RecallConfig | None = None,
    now: datetime | None = None,
    deck_id: str | None = None,
) -> dict[str, Any]:
    """Accept multiple suggestions, returning per-candidate outcomes.

    ``contexts`` maps candidate id -> answer-generation context so each card is
    grounded in its own source note.
    """
    now = now or SystemClock().now()
    results: list[dict[str, Any]] = []
    accepted = 0
    failed = 0

    for candidate_id in candidate_ids:
        try:
            result = accept_candidate(
                user_id,
                candidate_id,
                repo=repo,
                model=model,
                context=(contexts or {}).get(candidate_id),
                recall_config=recall_config,
                now=now,
                deck_id=deck_id,
            )
        except LookupError:
            failed += 1
            results.append(
                {"candidate_id": candidate_id, "status": "failed", "error": "candidate_not_found"}
            )
        except ValueError as exc:
            failed += 1
            results.append(
                {"candidate_id": candidate_id, "status": "failed", "error": str(exc)}
            )
        else:
            accepted += 1
            results.append(
                {
                    "candidate_id": candidate_id,
                    "status": result["status"],
                    "card": result.get("card"),
                    "error": None,
                }
            )

    return {"accepted": accepted, "failed": failed, "results": results}
