from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from ..deps import get_current_user_id
from ...schemas.models import (
    DueCardsResponse,
    RecallBulkAcceptRequest,
    RecallBulkAcceptResponse,
    RecallBulkDeckAssignRequest,
    RecallCardBulkUpdateRequest,
    RecallCardListResponse,
    RecallCardUpdateRequest,
    RecallCardResponse,
    RecallDecisionRequest,
    RecallDecisionResponse,
    RecallDeckCreate,
    RecallDeckListResponse,
    RecallDeckResponse,
    RecallDeckUpdate,
    RecallGradeRequest,
    RecallReviewResult,
    RecallSuggestionListResponse,
    RecallSuggestionResponse,
    RecallSuggestionUpdateRequest,
    ReviewHistoryResponse,
)
from ...domain.recall.question_service import (
    build_context,
    generate_answer_for_candidate,
)
from ...domain.recall.card_library import (
    browse_cards,
    bulk_update_cards,
    update_card,
)
from ...domain.recall.deck_service import (
    archive_deck,
    assign_candidates_to_deck,
    create_deck,
    get_active_deck,
    list_cards,
    list_decks_with_stats,
    move_card_to_deck,
    restore_deck,
    update_deck,
)
from ...domain.recall.review_service import (
    accept_candidate,
    accept_candidates,
    list_suggestions,
    reject_candidate,
    review_card,
    update_suggestion,
)
from ...domain.memory.services import query_entities_by_source_note
from ...infrastructure.db.recall_repository import get_recall_repository
from ...infrastructure.db.supabase_client import get_note_item
from ...infrastructure.llm.gemini_client import get_chat_model

router = APIRouter()


def _suggestion_context(user_id: str, candidate: dict) -> dict:
    """Grounding context for on-demand answer generation on a single candidate."""
    note_text = ""
    source_note_id = candidate.get("source_note_id")
    if source_note_id:
        try:
            note = get_note_item(user_id=user_id, note_id=source_note_id) or {}
            note_text = note.get("raw_text") or ""
        except Exception:  # noqa: BLE001 - generation can proceed without it
            note_text = ""

    entity_names: list[str] = []
    if source_note_id:
        try:
            entity_rows = query_entities_by_source_note(user_id=user_id, note_id=source_note_id)
            entity_names = [row.get("name") for row in entity_rows if row.get("name")]
        except Exception:  # noqa: BLE001 - context is best-effort
            entity_names = []

    return build_context(note_text, entity_names=entity_names)


def _to_suggestion(row: dict) -> RecallSuggestionResponse:
    return RecallSuggestionResponse(
        candidate_id=row["candidate_id"],
        question=row.get("prompt") or "",
        answer=row.get("answer"),
        item_type=row.get("item_type") or "fact",
        source_note_id=row.get("source_note_id"),
        deck_id=row.get("deck_id"),
        score=row.get("score"),
        importance=row.get("importance"),
        durability=row.get("durability"),
        created_at=row.get("created_at"),
    )


@router.get("/candidates", response_model=RecallSuggestionListResponse)
def get_candidates(
    status: str = Query(default="suggested"),
    source_note_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user_id: str = Depends(get_current_user_id),
):
    repo = get_recall_repository()
    rows = repo.query_candidates(
        user_id, status=status, limit=limit, source_note_id=source_note_id
    )
    suggestions = [_to_suggestion(row) for row in rows if row.get("prompt")]
    return RecallSuggestionListResponse(suggestions=suggestions, total=len(suggestions))


@router.patch("/candidates/{candidate_id}", response_model=RecallSuggestionResponse)
def patch_suggestion(
    candidate_id: str,
    payload: RecallSuggestionUpdateRequest,
    user_id: str = Depends(get_current_user_id),
):
    try:
        row = update_suggestion(
            user_id,
            candidate_id,
            repo=get_recall_repository(),
            question=payload.question,
            answer=payload.answer,
            deck_id=payload.deck_id,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="candidate_not_found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _to_suggestion(row)


@router.post("/candidates/accept-batch", response_model=RecallBulkAcceptResponse)
def post_accept_candidates(
    payload: RecallBulkAcceptRequest,
    user_id: str = Depends(get_current_user_id),
):
    repo = get_recall_repository()
    candidate_ids = list(dict.fromkeys(payload.candidate_ids))
    contexts: dict[str, dict] = {}
    for candidate_id in candidate_ids:
        candidate = repo.get_candidate(user_id, candidate_id)
        if candidate:
            contexts[candidate_id] = _suggestion_context(user_id, candidate)

    result = accept_candidates(
        user_id,
        candidate_ids,
        repo=repo,
        model=get_chat_model(),
        contexts=contexts,
        deck_id=payload.deck_id,
    )
    return RecallBulkAcceptResponse(**result)


@router.post("/candidates/{candidate_id}/accept", response_model=RecallDecisionResponse)
def post_accept_candidate(
    candidate_id: str,
    payload: RecallDecisionRequest | None = None,
    user_id: str = Depends(get_current_user_id),
):
    repo = get_recall_repository()
    try:
        candidate = repo.get_candidate(user_id, candidate_id)
        if candidate is None:
            raise LookupError("candidate_not_found")
        result = accept_candidate(
            user_id,
            candidate_id,
            repo=repo,
            model=get_chat_model(),
            context=_suggestion_context(user_id, candidate),
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="candidate_not_found")
    except ValueError as exc:
        # Generation failures are upstream errors, not a bad request.
        code = 502 if str(exc).startswith("answer_generation_failed") else 409
        raise HTTPException(status_code=code, detail=str(exc))
    return RecallDecisionResponse(
        status=result["status"],
        candidate_id=candidate_id,
        card=RecallCardResponse(**result["card"]) if result.get("card") else None,
    )


@router.post("/candidates/{candidate_id}/answer", response_model=RecallSuggestionResponse)
def post_generate_candidate_answer(
    candidate_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Generate (or return) a candidate's answer on demand.

    Answers are no longer produced during note processing: the client calls
    this when the user reveals the answer or accepts the suggestion.
    """
    repo = get_recall_repository()
    candidate = repo.get_candidate(user_id, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="candidate_not_found")

    try:
        row = generate_answer_for_candidate(
            user_id,
            candidate_id,
            model=get_chat_model(),
            repo=repo,
            context=_suggestion_context(user_id, candidate),
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="candidate_not_found")
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return _to_suggestion(row)


@router.post("/candidates/{candidate_id}/reject", response_model=RecallDecisionResponse)
def post_reject_candidate(
    candidate_id: str,
    payload: RecallDecisionRequest | None = None,
    user_id: str = Depends(get_current_user_id),
):
    try:
        result = reject_candidate(user_id, candidate_id, repo=get_recall_repository())
    except LookupError:
        raise HTTPException(status_code=404, detail="candidate_not_found")
    return RecallDecisionResponse(status=result["status"], candidate_id=candidate_id)


# ---------------------------------------------------------------------------
# Decks
# ---------------------------------------------------------------------------

def _to_deck(row: dict) -> RecallDeckResponse:
    return RecallDeckResponse(**row)


@router.get("/decks", response_model=RecallDeckListResponse)
def get_decks(
    include_archived: bool = Query(default=False),
    user_id: str = Depends(get_current_user_id),
):
    decks = list_decks_with_stats(
        user_id,
        repo=get_recall_repository(),
        include_archived=include_archived,
    )
    return RecallDeckListResponse(decks=[_to_deck(deck) for deck in decks], total=len(decks))


@router.post("/decks", response_model=RecallDeckResponse, status_code=201)
def post_deck(
    payload: RecallDeckCreate,
    user_id: str = Depends(get_current_user_id),
):
    try:
        deck = create_deck(
            user_id,
            repo=get_recall_repository(),
            name=payload.name,
            description=payload.description,
            color=payload.color,
        )
    except ValueError as exc:
        code = 409 if str(exc) == "deck_name_taken" else 422
        raise HTTPException(status_code=code, detail=str(exc))
    return _to_deck({**deck, "total_cards": 0, "due_cards": 0, "new_cards": 0, "suspended_cards": 0})


@router.patch("/decks/{deck_id}", response_model=RecallDeckResponse)
def patch_deck(
    deck_id: str,
    payload: RecallDeckUpdate,
    user_id: str = Depends(get_current_user_id),
):
    repo = get_recall_repository()
    try:
        deck = update_deck(
            user_id,
            deck_id,
            repo=repo,
            name=payload.name,
            description=payload.description,
            description_provided="description" in payload.model_fields_set,
            color=payload.color,
            sort_order=payload.sort_order,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="deck_not_found")
    except ValueError as exc:
        code = 409 if str(exc) == "deck_name_taken" else 422
        raise HTTPException(status_code=code, detail=str(exc))

    stats = next(
        (row for row in list_decks_with_stats(user_id, repo=repo) if row["deck_id"] == deck_id),
        {},
    )
    return _to_deck({**deck, **stats})


@router.delete("/decks/{deck_id}", response_model=RecallDeckResponse)
def delete_deck(
    deck_id: str,
    user_id: str = Depends(get_current_user_id),
):
    repo = get_recall_repository()
    try:
        deck = archive_deck(user_id, deck_id, repo=repo)
    except LookupError:
        raise HTTPException(status_code=404, detail="deck_not_found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _to_deck(deck)


@router.post("/decks/{deck_id}/restore", response_model=RecallDeckResponse)
def post_restore_deck(
    deck_id: str,
    user_id: str = Depends(get_current_user_id),
):
    repo = get_recall_repository()
    try:
        deck = restore_deck(user_id, deck_id, repo=repo)
    except LookupError:
        raise HTTPException(status_code=404, detail="deck_not_found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _to_deck(deck)


@router.post("/candidates/assign-deck", response_model=RecallSuggestionListResponse)
def post_assign_candidates_deck(
    payload: RecallBulkDeckAssignRequest,
    user_id: str = Depends(get_current_user_id),
):
    repo = get_recall_repository()
    try:
        rows = assign_candidates_to_deck(
            user_id,
            list(dict.fromkeys(payload.candidate_ids)),
            payload.deck_id,
            repo=repo,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="deck_not_found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    suggestions = [_to_suggestion(row) for row in rows if row.get("prompt")]
    return RecallSuggestionListResponse(suggestions=suggestions, total=len(suggestions))


@router.get("/cards", response_model=RecallCardListResponse)
def get_cards(
    deck_id: str | None = Query(default=None),
    include_not_due: bool = Query(default=False),
    status: str | None = Query(default="active"),
    state: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100),
    due: Literal["due", "not_due"] | None = Query(default=None),
    source_note_id: str | None = Query(default=None),
    sort: Literal["due", "newest", "reviews", "lapses"] = Query(default="due"),
    limit: int = Query(default=200, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id: str = Depends(get_current_user_id),
):
    effective_due = due
    if effective_due is None and not include_not_due:
        effective_due = "due"
    try:
        result = browse_cards(
            user_id,
            repo=get_recall_repository(),
            deck_id=deck_id,
            status=None if status in (None, "all") else status,
            state=state,
            q=q,
            due=effective_due,
            source_note_id=source_note_id,
            sort=sort,
            limit=limit,
            offset=offset,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="deck_not_found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return RecallCardListResponse(
        cards=[RecallCardResponse(**card) for card in result["cards"]],
        total=result["total"],
    )


@router.patch("/cards/bulk", response_model=RecallCardListResponse)
def patch_cards_bulk(
    payload: RecallCardBulkUpdateRequest,
    user_id: str = Depends(get_current_user_id),
):
    repo = get_recall_repository()
    try:
        cards = bulk_update_cards(
            user_id,
            list(payload.card_ids),
            repo=repo,
            deck_id=payload.deck_id,
            deck_provided="deck_id" in payload.model_fields_set,
            status=payload.status,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="deck_not_found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return RecallCardListResponse(
        cards=[RecallCardResponse(**card) for card in cards],
        total=len(cards),
    )


@router.patch("/cards/{card_id}", response_model=RecallCardResponse)
def patch_card(
    card_id: str,
    payload: RecallCardUpdateRequest,
    user_id: str = Depends(get_current_user_id),
):
    try:
        card = update_card(
            user_id,
            card_id,
            repo=get_recall_repository(),
            deck_id=payload.deck_id,
            deck_provided="deck_id" in payload.model_fields_set,
            status=payload.status,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="card_or_deck_not_found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return RecallCardResponse(**card)


@router.get("/due", response_model=DueCardsResponse)
def get_due_cards(
    deck_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user_id: str = Depends(get_current_user_id),
):
    try:
        cards = list_cards(
            user_id,
            repo=get_recall_repository(),
            deck_id=deck_id,
            include_not_due=False,
            status="active",
            limit=limit,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="deck_not_found")
    return DueCardsResponse(
        cards=[RecallCardResponse(**card) for card in cards],
        total_due=len(cards),
    )


@router.post("/cards/{card_id}/review", response_model=RecallReviewResult)
def post_review_card(
    card_id: str,
    payload: RecallGradeRequest,
    user_id: str = Depends(get_current_user_id),
):
    try:
        result = review_card(
            user_id,
            card_id,
            payload.grade,
            repo=get_recall_repository(),
            elapsed_ms=payload.elapsed_ms,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="card_not_found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return RecallReviewResult(
        card=RecallCardResponse(**result["card"]),
        history=ReviewHistoryResponse(**result["history"]) if result.get("history") else None,
    )
