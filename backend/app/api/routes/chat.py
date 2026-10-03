import asyncio

from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_current_user_id
from ...domain.chat.memory import load_recent_chat_messages
from ...domain.chat.services import handle_chat_message
from ...schemas.models import ChatMessageRequest, ChatMessageResponse, ChatThreadResponse
from ...infrastructure.db.supabase_client import get_chat_thread_item


router = APIRouter()


@router.post("/message", response_model=ChatMessageResponse)
async def send_chat_message(payload: ChatMessageRequest, user_id: str = Depends(get_current_user_id)):
    try:
        # handle_chat_message is synchronous (blocking Gemini/Supabase calls);
        # run it off the event loop thread so concurrent requests don't queue
        # behind each other's I/O.
        return await asyncio.to_thread(
            handle_chat_message,
            user_id=user_id,
            message=payload.message,
            thread_id=payload.thread_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/threads/{thread_id}", response_model=ChatThreadResponse)
async def get_chat_thread(thread_id: str, user_id: str = Depends(get_current_user_id)):
    thread = await asyncio.to_thread(get_chat_thread_item, user_id=user_id, thread_id=thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Chat thread not found")

    messages = await asyncio.to_thread(
        load_recent_chat_messages, user_id=user_id, thread_id=thread_id, limit=100
    )
    return {
        "thread_id": thread.get("thread_id"),
        "user_id": thread.get("user_id"),
        "title": thread.get("title"),
        "summary": thread.get("summary"),
        "summary_updated_at": thread.get("summary_updated_at"),
        "created_at": thread.get("created_at"),
        "updated_at": thread.get("updated_at"),
        "messages": messages,
    }
