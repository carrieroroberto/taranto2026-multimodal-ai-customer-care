from fastapi import APIRouter

from backend.app.repositories.persistence_repository import (
    ensure_conversation,
    get_conversation_messages,
)
from backend.app.schemas.conversation import (
    ConversationMessagesResponseDTO,
    ConversationRequestDTO,
    ConversationResponseDTO,
)


router = APIRouter(tags=["conversations"])


@router.post("/conversations", response_model=ConversationResponseDTO)
def start_conversation(request: ConversationRequestDTO) -> ConversationResponseDTO:
    conversation_id = ensure_conversation(session_id=request.session_id)
    return ConversationResponseDTO(
        session_id=request.session_id,
        conversation_id=conversation_id,
    )


@router.get(
    "/conversations/{session_id}/messages",
    response_model=ConversationMessagesResponseDTO,
)
def conversation_messages(session_id: str) -> ConversationMessagesResponseDTO:
    conversation_id = ensure_conversation(session_id=session_id)
    return ConversationMessagesResponseDTO(
        session_id=session_id,
        conversation_id=conversation_id,
        messages=get_conversation_messages(session_id),
    )
