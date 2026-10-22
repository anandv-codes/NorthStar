import uuid
import logging
import os
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from ..deps import get_current_user_id
from ...schemas.models import (
    NoteCreateRequest,
    NoteListResponse,
    NoteStatusResponse,
    NoteMemoryResponse,
    NoteRecallToggleRequest,
    NoteRecallToggleResponse,
)
from ...infrastructure.db.supabase_client import (
    get_note_item,
    get_note_repository,
    put_note_item,
    update_note_item,
)
from ...infrastructure.db.recall_repository import get_recall_repository
from ...infrastructure.llm.gemini_client import get_chat_model
from ...domain.recall.question_service import build_context, generate_questions_for_note
from ...domain.memory.services import (
    query_latest_extraction_run_for_note,
    query_tasks_by_source_note,
    query_facts_by_source_note,
    query_questions_by_source_note,
    query_decisions_by_source_note,
    query_risks_by_source_note,
    query_concepts_by_source_note,
    query_entities_by_source_note,
)
from ...infrastructure.queue.sqs_client import send_note_job
from ...infrastructure.queue.sqs_poller import poll_sqs_messages, delete_sqs_message
from ...workers.note_processor import process_sqs_message

logger = logging.getLogger(__name__)
PROCESS_NOTES_INLINE = os.getenv("PROCESS_NOTES_INLINE", "false").lower() == "true"

router = APIRouter()


def _process_note_job(job: dict) -> None:
    """Run the inline note pipeline after the response has been sent.

    Previously this ran inside the POST handler, so the browser waited for
    retrieval + extraction + question generation (~10-40s). Starlette runs
    background tasks in-process right after the response, so breakpoints in
    ``note_processor`` still hit while the client gets its 202 immediately.
    """
    failed_status = {"status": "failed", "recall_status": "failed"}
    try:
        process_sqs_message(job)
    except Exception:
        logger.exception(
            "Inline note processing failed: note_id=%s user_id=%s",
            job.get("note_id"),
            job.get("user_id"),
        )
        try:
            update_note_item(job["user_id"], job["note_id"], failed_status)
        except Exception as exc:  # noqa: BLE001 - best-effort failure marker
            logger.warning("Could not mark note %s as failed: %s", job.get("note_id"), exc)


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_note(
    payload: NoteCreateRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
):
    note_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    logger.info(f"create_note: user_id={user_id}, note_id={note_id}")

    item = {
        "note_id": note_id,
        "user_id": user_id,
        "status": "processing",
        "created_at": created_at,
        "raw_text": payload.text,
        "metadata": payload.metadata,
        "recall_enabled": payload.recall_enabled,
        "recall_status": "pending" if payload.recall_enabled else "off",
    }

    logger.info("Saving note to Supabase")
    put_note_item(item)                         #Save initial note with status "processing"

    if not PROCESS_NOTES_INLINE:
        # The EC2 SQS worker (`app.workers.sqs_consumer`) consumes this job.
        logger.info("Sending SQS job")
        send_note_job(
            {
                "user_id": user_id,
                "note_id": note_id,
                "created_at": created_at,
                "raw_text": payload.text,
            }
        )
    else:
        # Local debug helper: process in-process so breakpoints in note_processor hit reliably.
        # Queued as a background task so the POST returns immediately.
        logger.info("Processing note in-process (background task)")
        background_tasks.add_task(
            _process_note_job,
            {
                "user_id": user_id,
                "note_id": note_id,
                "created_at": created_at,
                "raw_text": payload.text,
            },
        )

    return {"note_id": note_id, "status": "processing"}


@router.get("", response_model=NoteListResponse)
def list_notes(
    q: str | None = Query(default=None, max_length=100),
    recall: Literal["on", "off"] | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    created_after: str | None = Query(default=None),
    created_before: str | None = Query(default=None),
    sort: Literal["newest", "oldest"] = Query(default="newest"),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    user_id: str = Depends(get_current_user_id),
):
    """Paginated note library with server-side search and filters."""
    return get_note_repository().query_notes_page(
        user_id,
        status=status_filter,
        recall=recall,
        q=q,
        created_after=created_after,
        created_before=created_before,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@router.get("/{note_id}", response_model=NoteStatusResponse)
def get_note_status(note_id: str, user_id: str = Depends(get_current_user_id)):
    logger.info(f"get_note_status: note_id={note_id}, user_id={user_id}")
    item = get_note_item(user_id=user_id, note_id=note_id)
    if not item:
        raise HTTPException(status_code=404, detail="Note not found")
    logger.info(f"Note status: {item.get('status')}")
    return item


@router.get("/{note_id}/memory", response_model=NoteMemoryResponse)
def get_note_memory(note_id: str, user_id: str = Depends(get_current_user_id)):
    logger.info(f"get_note_memory: note_id={note_id}, user_id={user_id}")
    note = get_note_item(user_id=user_id, note_id=note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    extraction_run = query_latest_extraction_run_for_note(user_id=user_id, note_id=note_id)
    tasks = query_tasks_by_source_note(user_id=user_id, note_id=note_id)
    facts = query_facts_by_source_note(user_id=user_id, note_id=note_id)
    questions = query_questions_by_source_note(user_id=user_id, note_id=note_id)
    decisions = query_decisions_by_source_note(user_id=user_id, note_id=note_id)
    risks = query_risks_by_source_note(user_id=user_id, note_id=note_id)
    concepts = query_concepts_by_source_note(user_id=user_id, note_id=note_id)
    entities = query_entities_by_source_note(user_id=user_id, note_id=note_id)

    payload = {
        "note": note,
        "extraction_run": extraction_run or None,
        "tasks": tasks,
        "facts": facts,
        "questions": questions,
        "decisions": decisions,
        "risks": risks,
        "concepts": concepts,
        "entities": entities,
    }
    logger.info(f"memory snapshot ready: tasks={len(tasks)}, facts={len(facts)}, questions={len(questions)}, decisions={len(decisions)}, risks={len(risks)}, concepts={len(concepts)}, entities={len(entities)}")
    return payload


@router.patch("/{note_id}/recall", response_model=NoteRecallToggleResponse)
def toggle_note_recall(
    note_id: str,
    payload: NoteRecallToggleRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Enable/disable recall question generation for a note.

    Enabling generates questions for the note's already-scored candidates
    synchronously (one LLM call per candidate); disabling stops future
    generation but leaves existing suggestions/cards intact.
    """
    logger.info(f"toggle_note_recall: note_id={note_id}, enabled={payload.enabled}")
    note = get_note_item(user_id=user_id, note_id=note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    questions_generated = 0
    recall_status = "off"
    if payload.enabled:
        update_note_item(user_id, note_id, {"recall_enabled": True, "recall_status": "pending"})
        recall_status = "ready"
        try:
            entity_rows = query_entities_by_source_note(user_id=user_id, note_id=note_id)
            entity_names = [e.get("name") for e in entity_rows if e.get("name")]
            context = build_context(note.get("raw_text", ""), entity_names=entity_names)
            results = generate_questions_for_note(
                user_id,
                note_id,
                context,
                model=get_chat_model(),
                repo=get_recall_repository(),
            )
            questions_generated = sum(1 for r in results if r["status"] == "suggested")
            logger.info(f"Recall questions generated on toggle: {questions_generated}")
        except Exception as exc:
            recall_status = "failed"
            logger.warning(f"Question generation on toggle failed; continuing: {exc}")
    else:
        update_note_item(user_id, note_id, {"recall_enabled": False, "recall_status": "off"})

    suggestions_total = len(
        get_recall_repository().query_candidates(
            user_id, status="suggested", source_note_id=note_id
        )
    )
    # Still-processing note: candidates may not exist yet. Leave it pending so
    # the worker (which re-reads the flag) finishes generation instead of the
    # UI claiming "ready" with zero suggestions.
    if (
        payload.enabled
        and recall_status == "ready"
        and suggestions_total == 0
        and note.get("status") != "completed"
    ):
        recall_status = "pending"
    if payload.enabled:
        update_note_item(user_id, note_id, {"recall_status": recall_status})

    return NoteRecallToggleResponse(
        note_id=note_id,
        enabled=payload.enabled,
        recall_status=recall_status,
        questions_generated=questions_generated,
        suggestions_total=suggestions_total,
    )


@router.post("/poll/process-jobs")
def poll_and_process_jobs(_: str = Depends(get_current_user_id)):
    """Poll SQS queue for pending note jobs and process them synchronously."""
    logger.info("[HANDLER] Starting SQS polling")
    messages = poll_sqs_messages(max_messages=10, wait_time_seconds=1)

    if not messages:
        logger.info("[HANDLER] No messages in queue")
        return {"processed": 0, "failed": 0}

    processed = 0
    failed = 0

    for message in messages:
        try:
            logger.info(f"[HANDLER] Processing message {message['message_id']}")
            result = process_sqs_message(message["body"])
            logger.info(f"[HANDLER] Message processed successfully: {result}")

            if delete_sqs_message(message["receipt_handle"]):
                processed += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"[HANDLER] Error processing message {message['message_id']}: {e}")
            failed += 1

    logger.info(f"[HANDLER] Polling complete - processed={processed}, failed={failed}")
    return {"processed": processed, "failed": failed}
