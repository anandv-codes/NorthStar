import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status
from ..schemas import NoteCreateRequest, NoteStatusResponse
from ..services.supabase import put_note_item, get_note_item
from ..services.sqs import send_note_job

router = APIRouter()

@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_note(payload: NoteCreateRequest):
    note_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    item = {
        "PK": f"USER#{payload.user_id}",
        "SK": f"NOTE#{note_id}",
        "note_id": note_id,
        "user_id": payload.user_id,
        "status": "processing",
        "created_at": created_at,
        "raw_text": payload.text,
        "metadata": payload.metadata,
    }

    put_note_item(item)

    send_note_job(
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
    item = get_note_item(user_id=user_id, note_id=note_id)
    if not item:
        raise HTTPException(status_code=404, detail="Note not found")
    return item
