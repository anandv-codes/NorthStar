from fastapi import APIRouter, Depends, HTTPException, Query

from ..deps import get_current_user_id
from ...schemas.models import (
    DueCardsResponse,
    RecallBulkAcceptRequest,
    RecallBulkAcceptResponse,
    RecallCardResponse,
    RecallDecisionRequest,
    RecallDecisionResponse,
    RecallGradeRequest,
    RecallReviewResult,
    RecallSuggestionListResponse,
    RecallSuggestionResponse,
    RecallSuggestionUpdateRequest,
    ReviewHistoryResponse,
)
from ...domain.recall.review_service import (
    accept_candidate,
    accept_candidates,
    due_cards,
    list_suggestions,
    reject_candidate,
    review_card,
    update_suggestion,
)
from ...infrastructure.db.recall_repository import get_recall_repository

router = APIRouter()


def _to_suggestion(row: dict) -> RecallSuggestionResponse:
    return RecallSuggestionResponse(
        candidate_id=row["candidate_id"],
        question=row.get("prompt") or "",
        answer=row.get("answer"),
        item_type=row.get("item_type") or "fact",
        source_note_id=row.get("source_note_id"),
        score=row.get("score"),
        importance=row.get("importance"),
        durability=row.get("durability"),
        created_at=row.get("created_at"),
    )


@router.get("/candidates", response_model=RecallSuggestionListResponse)
def get_candidates(
    status: str = Query(default="suggested"),
    limit: int = Query(default=50, ge=1, le=200),
    user_id: str = Depends(get_current_user_id),
):
    repo = get_recall_repository()
    rows = repo.query_candidates(user_id, status=status, limit=limit)
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
    result = accept_candidates(
        user_id,
        list(dict.fromkeys(payload.candidate_ids)),
        repo=get_recall_repository(),
    )
    return RecallBulkAcceptResponse(**result)


@router.post("/candidates/{candidate_id}/accept", response_model=RecallDecisionResponse)
def post_accept_candidate(
    candidate_id: str,
    payload: RecallDecisionRequest | None = None,
    user_id: str = Depends(get_current_user_id),
):
    try:
        result = accept_candidate(
            user_id, candidate_id, repo=get_recall_repository()
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="candidate_not_found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return RecallDecisionResponse(
        status=result["status"],
        candidate_id=candidate_id,
        card=RecallCardResponse(**result["card"]) if result.get("card") else None,
    )


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


@router.get("/due", response_model=DueCardsResponse)
def get_due_cards(
    limit: int = Query(default=50, ge=1, le=200),
    user_id: str = Depends(get_current_user_id),
):
    cards = due_cards(user_id, repo=get_recall_repository(), limit=limit)
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
