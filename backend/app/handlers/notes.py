import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from ..schemas import NoteCreateRequest, NoteStatusResponse
from ..services.supabase import put_note_item, get_note_item
from ..services.sqs import send_note_job

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

    return {"note_id": note_id, "status": "processing"}

@router.get("/{note_id}", response_model=NoteStatusResponse)
def get_note_status(note_id: str, user_id: str):
    print(f"[HANDLER] get_note_status: note_id={note_id}, user_id={user_id}")
    item = get_note_item(user_id=user_id, note_id=note_id)
    if not item:
        raise HTTPException(status_code=404, detail="Note not found")
    print(f"[HANDLER] Note status: {item.get('status')}")
    return item
