from datetime import datetime
from typing import Literal

from pydantic import BaseModel

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
    content: str | None = None
    caption: str | None = None
    media_url: str | None = None
    sources: list[SourceDTO] | None = None
    satisfaction: bool | None = None
    ticket_opened: bool = False
    created_at: datetime


class ConversationMessagesResponseDTO(BaseModel):
    session_id: str
    conversation_id: str
    messages: list[PersistedMessageDTO]


class ConversationMessageCreateDTO(BaseModel):
    role: Literal["user", "bot"]
    content: str | None = None
    caption: str | None = None
    message_type: Literal["text", "image", "audio"] = "text"
    media_url: str | None = None
    sources: list[SourceDTO] | None = None


class ConversationMessageDeleteDTO(BaseModel):
    message_ids: list[str]
