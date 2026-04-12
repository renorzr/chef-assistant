from fastapi import APIRouter, Depends, HTTPException

from database import get_db
from schemas import ChatMessageRequest, ChatMessageResponse, ChatHistoryResponse
from services.chat_service import send_chat_message_via_openclaw, ChatServiceError, list_recent_chat_messages
from sqlalchemy.orm import Session

router = APIRouter()


@router.post("/chat/messages", response_model=ChatMessageResponse)
def create_chat_message(payload: ChatMessageRequest, db: Session = Depends(get_db)):
    try:
        return send_chat_message_via_openclaw(db, payload)
    except ChatServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/chat/sessions/{session_id}/messages", response_model=ChatHistoryResponse)
def get_chat_messages(session_id: str, limit: int = 20, db: Session = Depends(get_db)):
    return list_recent_chat_messages(db, session_id, limit=limit)
