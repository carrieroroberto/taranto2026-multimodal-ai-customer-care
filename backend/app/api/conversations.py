from fastapi import APIRouter

from backend.app.repositories.persistence_repository import (
    delete_conversation_messages,
    ensure_conversation,
    get_conversation_messages,
    save_message,
)
from backend.app.schemas.conversation import (
    ConversationMessageCreateDTO,
    ConversationMessageDeleteDTO,
    ConversationMessagesResponseDTO,
    ConversationRequestDTO,
    ConversationResponseDTO,
    PersistedMessageDTO,
)


router = APIRouter(tags=["conversations"])


@router.post("/conversations", response_model=ConversationResponseDTO)
def start_conversation(request: ConversationRequestDTO) -> ConversationResponseDTO:
    import uuid
    session_id = request.session_id or str(uuid.uuid4())
    conversation_id = ensure_conversation(session_id=session_id)
    return ConversationResponseDTO(
        session_id=session_id,
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


@router.post(
    "/conversations/{session_id}/messages",
    response_model=PersistedMessageDTO,
)
def create_conversation_message(
    session_id: str,
    request: ConversationMessageCreateDTO,
) -> PersistedMessageDTO:
    ensure_conversation(session_id=session_id)
    saved = save_message(
        session_id=session_id,
        role=request.role,
        content=request.content,
        message_type=request.message_type,
        media_url=request.media_url,
        sources=[source.model_dump() for source in request.sources] if request.sources else None,
    )
    return PersistedMessageDTO(**saved)


@router.delete("/conversations/{session_id}/messages")
def delete_conversation_message_batch(
    session_id: str,
    request: ConversationMessageDeleteDTO,
):
    deleted_ids = delete_conversation_messages(session_id, request.message_ids)
    return {"deleted_ids": deleted_ids}
