from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..deps import get_current_user_id
from ...domain.commitments.services import (
    MAX_ACTIVE_COMMITMENTS,
    CommitmentError,
    CommitmentLimitError,
    CommitmentNotFoundError,
    CommitmentStateError,
    create_commitment,
    delete_commitment,
    delete_contribution,
    get_commitment,
    list_commitments,
    list_contributions,
    update_commitment,
    update_contribution,
)
from ...schemas.models import (
    CommitmentContributionResponse,
    CommitmentContributionUpdateRequest,
    UserCommitmentCreateRequest,
    UserCommitmentListResponse,
    UserCommitmentResponse,
    UserCommitmentUpdateRequest,
)

router = APIRouter()


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Commitment not found")


@router.get("", response_model=UserCommitmentListResponse)
def get_commitments(
    status_filter: Literal["active", "completed"] | None = Query(
        default=None, alias="status"
    ),
    user_id: str = Depends(get_current_user_id),
):
    rows = list_commitments(user_id=user_id, status=status_filter)
    active_count = sum(1 for row in rows if row.get("status") == "active")
    return {
        "commitments": rows,
        "active_count": active_count,
        "max_active": MAX_ACTIVE_COMMITMENTS,
    }


@router.post("", response_model=UserCommitmentResponse, status_code=status.HTTP_201_CREATED)
def post_commitment(
    payload: UserCommitmentCreateRequest,
    user_id: str = Depends(get_current_user_id),
):
    try:
        return create_commitment(user_id=user_id, text=payload.text)
    except CommitmentLimitError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CommitmentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{commitment_id}", response_model=UserCommitmentResponse)
def get_commitment_by_id(
    commitment_id: str,
    user_id: str = Depends(get_current_user_id),
):
    row = get_commitment(user_id=user_id, commitment_id=commitment_id)
    if row is None:
        raise _not_found()
    return row


@router.patch("/{commitment_id}", response_model=UserCommitmentResponse)
def patch_commitment(
    commitment_id: str,
    payload: UserCommitmentUpdateRequest,
    user_id: str = Depends(get_current_user_id),
):
    updates = payload.model_dump(exclude_unset=True)
    try:
        row = update_commitment(
            user_id=user_id, commitment_id=commitment_id, updates=updates
        )
    except CommitmentStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CommitmentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not row:
        raise _not_found()
    return row


@router.delete("/{commitment_id}")
def remove_commitment(
    commitment_id: str,
    user_id: str = Depends(get_current_user_id),
):
    if not delete_commitment(user_id=user_id, commitment_id=commitment_id):
        raise _not_found()
    return {"deleted": True}


@router.get(
    "/{commitment_id}/contributions",
    response_model=list[CommitmentContributionResponse],
)
def get_contributions(
    commitment_id: str,
    user_id: str = Depends(get_current_user_id),
):
    try:
        return list_contributions(user_id=user_id, commitment_id=commitment_id)
    except CommitmentNotFoundError as exc:
        raise _not_found() from exc


@router.patch(
    "/contributions/{contribution_id}",
    response_model=CommitmentContributionResponse,
)
def patch_contribution(
    contribution_id: str,
    payload: CommitmentContributionUpdateRequest,
    user_id: str = Depends(get_current_user_id),
):
    try:
        return update_contribution(
            user_id=user_id,
            contribution_id=contribution_id,
            comment=payload.comment,
        )
    except CommitmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CommitmentStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CommitmentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/contributions/{contribution_id}")
def remove_contribution(
    contribution_id: str,
    user_id: str = Depends(get_current_user_id),
):
    try:
        deleted = delete_contribution(
            user_id=user_id, contribution_id=contribution_id
        )
    except CommitmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CommitmentStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Contribution not found")
    return {"deleted": True}
