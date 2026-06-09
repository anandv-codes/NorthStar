from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

class NoteCreateRequest(BaseModel):
    user_id: str = Field(..., description="User ID for the note")
    text: str = Field(..., min_length=1, description="Raw note text")
    metadata: Optional[dict] = Field(default_factory=dict)

class NoteStatusResponse(BaseModel):
    note_id: str
    user_id: str
    status: str
    created_at: datetime
    raw_text: str
    enriched_summary: Optional[str] = None
    action_items: Optional[List[str]] = None
    questions: Optional[List[str]] = None
