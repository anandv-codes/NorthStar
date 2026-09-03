from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_current_user_id
from ...domain.query_retrieval.services import retrieve_query_context
from ...schemas.models import QueryRetrievalRequest, QueryRetrievalResponse


router = APIRouter()


@router.post("/query", response_model=QueryRetrievalResponse)
def query_retrieval(payload: QueryRetrievalRequest, user_id: str = Depends(get_current_user_id)):
    try:
        return retrieve_query_context(
            user_id=user_id,
            query=payload.query,
            limit=payload.limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
