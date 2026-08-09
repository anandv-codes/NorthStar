from fastapi import APIRouter, HTTPException, Query

from ...schemas.models import (
    QuestionUpdateRequest,
    QuestionResponse,
    RecentMemoryResponse,
    RiskUpdateRequest,
    RiskResponse,
    TaskResponse,
    TaskUpdateRequest,
    ConceptResponse,
    ConceptUpdateRequest,
)
from ...domain.memory.services import (
    query_questions_for_user,
    query_recent_memory_for_user,
    query_risks_for_user,
    query_tasks_for_user,
    update_question_item,
    update_risk_item,
    update_task_item,
    query_concepts_for_user,
    update_concept_item,
)


router = APIRouter()


@router.get("/tasks", response_model=list[TaskResponse])
def get_tasks(user_id: str, status: str | None = None):
    return query_tasks_for_user(user_id=user_id, status=status)


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
def patch_task(task_id: str, user_id: str, payload: TaskUpdateRequest):
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="At least one field is required")

    updated = update_task_item(user_id=user_id, task_id=task_id, updates=updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    return updated


@router.get("/questions", response_model=list[QuestionResponse])
def get_questions(user_id: str, status: str | None = "open"):
    return query_questions_for_user(user_id=user_id, status=status)


@router.patch("/questions/{question_id}", response_model=QuestionResponse)
def patch_question(question_id: str, user_id: str, payload: QuestionUpdateRequest):
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="At least one field is required")

    try:
        updated = update_question_item(
            user_id=user_id,
            question_id=question_id,
            updates=updates,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not updated:
        raise HTTPException(status_code=404, detail="Question not found")
    return updated


@router.get("/risks", response_model=list[RiskResponse])
def get_risks(user_id: str, status: str | None = "open"):
    return query_risks_for_user(user_id=user_id, status=status)


@router.patch("/risks/{risk_id}", response_model=RiskResponse)
def patch_risk(risk_id: str, user_id: str, payload: RiskUpdateRequest):
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="At least one field is required")

    try:
        updated = update_risk_item(
            user_id=user_id,
            risk_id=risk_id,
            updates=updates,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not updated:
        raise HTTPException(status_code=404, detail="Risk not found")
    return updated

@router.get("/concepts", response_model=list[ConceptResponse])
def get_concepts(user_id: str, status: str | None = "open"):
    return query_concepts_for_user(user_id=user_id, status=status)

@router.patch("/concepts/{concept_id}", response_model=ConceptResponse)
def patch_concept(concept_id: str, user_id: str, payload: ConceptUpdateRequest):
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="At least one field is required")
    updated = update_concept_item(user_id=user_id, concept_id=concept_id, updates=updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Concept not found")
    return updated

@router.get("/memory/recent", response_model=RecentMemoryResponse)
def get_recent_memory(user_id: str, limit: int = Query(default=10, ge=1, le=50)):
    return query_recent_memory_for_user(user_id=user_id, limit=limit)
