import uuid
import logging
import os
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status
from ...schemas.models import NoteCreateRequest, NoteStatusResponse, NoteMemoryResponse
from ...infrastructure.db.supabase_client import put_note_item, get_note_item
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


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_note(payload: NoteCreateRequest):
    note_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    print(f"[HANDLER] create_note: user_id={payload.user_id}, note_id={note_id}")

    item = {
        "note_id": note_id,
        "user_id": payload.user_id,
        "status": "processing",
        "created_at": created_at,
        "raw_text": payload.text,
        "metadata": payload.metadata,
    }

    print(f"[HANDLER] Saving note to Supabase")
    put_note_item(item)                         #Save initial note with status "processing"


    print(f"[HANDLER] Sending SQS job")
    send_note_job(                          #Create SQS job for note processing lambda
        {
            "user_id": payload.user_id,
            "note_id": note_id,
            "created_at": created_at,
            "raw_text": payload.text,
        }
    )

    if PROCESS_NOTES_INLINE:
        # Local debug helper: process in-process so breakpoints in note_processor hit reliably.
        process_sqs_message(
            {
                "user_id": payload.user_id,
                "note_id": note_id,
                "created_at": created_at,
                "raw_text": payload.text,
            }
        )

    return {"note_id": note_id, "status": "processing"}


@router.get("/{note_id}", response_model=NoteStatusResponse)
def get_note_status(note_id: str, user_id: str):
    print(f"[HANDLER] get_note_status: note_id={note_id}, user_id={user_id}")
    item = get_note_item(user_id=user_id, note_id=note_id)
    if not item:
        raise HTTPException(status_code=404, detail="Note not found")
    print(f"[HANDLER] Note status: {item.get('status')}")
    return item


@router.get("/{note_id}/memory", response_model=NoteMemoryResponse)
def get_note_memory(note_id: str, user_id: str):
    print(f"[HANDLER] get_note_memory: note_id={note_id}, user_id={user_id}")
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
    print(f"[HANDLER] memory snapshot ready: tasks={len(tasks)}, facts={len(facts)}, questions={len(questions)}, decisions={len(decisions)}, risks={len(risks)}, concepts={len(concepts)}, entities={len(entities)}")
    return payload


@router.post("/poll/process-jobs")
def poll_and_process_jobs():
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
