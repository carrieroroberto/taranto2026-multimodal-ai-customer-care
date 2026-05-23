from datetime import datetime

from pydantic import BaseModel


class ConversationRequestDTO(BaseModel):
    session_id: str | None = None


class ConversationResponseDTO(BaseModel):
    session_id: str
    conversation_id: str


class PersistedMessageDTO(BaseModel):
    id: str
    conversation_id: str
    role: str
    type: str = "text"
    content: str
    satisfaction: bool | None = None
    created_at: datetime


class ConversationMessagesResponseDTO(BaseModel):
    session_id: str
    conversation_id: str
    messages: list[PersistedMessageDTO]
