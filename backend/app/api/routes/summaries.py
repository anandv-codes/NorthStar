from datetime import date

from fastapi import APIRouter, Depends, Query

from ..deps import get_current_user_id
from ...schemas.models import GenerateSummaryRequest, PeriodSummaryResponse, PeriodSummaryStatusResponse
from ...domain.summary.services import (
    generate_daily_summary,
    generate_weekly_summary,
    get_daily_summary_status,
    get_weekly_summary_status,
)

router = APIRouter()


def _to_response(result: dict) -> PeriodSummaryStatusResponse:
    summary = PeriodSummaryResponse(**result["summary"]) if result.get("summary") else None
    return PeriodSummaryStatusResponse(
        status=result["status"],
        summary=summary,
        notes_count=result["notes_count"],
        min_notes_required=result["min_notes_required"],
    )


@router.get("/daily", response_model=PeriodSummaryStatusResponse)
def get_daily_summary(
    summary_date: date | None = Query(default=None, alias="date"),
    user_id: str = Depends(get_current_user_id),
):
    return _to_response(get_daily_summary_status(user_id=user_id, day=summary_date))


@router.post("/daily/generate", response_model=PeriodSummaryStatusResponse)
def post_daily_summary(
    payload: GenerateSummaryRequest,
    user_id: str = Depends(get_current_user_id),
):
    return _to_response(
        generate_daily_summary(user_id=user_id, day=payload.period_start, regenerate=payload.regenerate)
    )


@router.get("/weekly", response_model=PeriodSummaryStatusResponse)
def get_weekly_summary(
    summary_date: date | None = Query(default=None, alias="date"),
    user_id: str = Depends(get_current_user_id),
):
    return _to_response(get_weekly_summary_status(user_id=user_id, any_day=summary_date))


@router.post("/weekly/generate", response_model=PeriodSummaryStatusResponse)
def post_weekly_summary(
    payload: GenerateSummaryRequest,
    user_id: str = Depends(get_current_user_id),
):
    return _to_response(
        generate_weekly_summary(user_id=user_id, any_day=payload.period_start, regenerate=payload.regenerate)
    )
