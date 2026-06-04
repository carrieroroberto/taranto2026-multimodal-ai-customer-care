from datetime import datetime

from pydantic import BaseModel, Field

from backend.app.schemas.chat import SourceDTO


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
    sources: list[SourceDTO] = Field(default_factory=list)
    satisfaction: bool | None = None
    ticket_opened: bool = False
    created_at: datetime


class ConversationMessagesResponseDTO(BaseModel):
    session_id: str
    conversation_id: str
    messages: list[PersistedMessageDTO]
