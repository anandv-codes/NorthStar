from fastapi import APIRouter, HTTPException

from ...domain.query_retrieval.services import retrieve_query_context
from ...schemas.models import QueryRetrievalRequest, QueryRetrievalResponse


router = APIRouter()


@router.post("/query", response_model=QueryRetrievalResponse)
def query_retrieval(payload: QueryRetrievalRequest):
    try:
        return retrieve_query_context(
            user_id=payload.user_id,
            query=payload.query,
            limit=payload.limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
