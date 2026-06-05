from typing import Literal

from pydantic import BaseModel, Field

from backend.app.schemas.ticket import TicketDraftDTO


class ChatRequestDTO(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = None
    visual_context: str | None = None
    planning_message: str | None = None
    language: str | None = None
    message_type: Literal["text", "image", "audio"] = "text"
    stored_user_content: str | None = None
    media_url: str | None = None


class SourceDTO(BaseModel):
    title: str | None = None
    url: str | None = None
    type: str | None = None
    maps_url: str | None = None


class ChatResponseDTO(BaseModel):
    session_id: str | None = None
    conversation_id: str | None = None

    user_message_id: str | None = None
    bot_message_id: str | None = None
    message_id: str | None = None  # Alias for bot_message_id as per latest request
    user_created_at: str | None = None
    bot_created_at: str | None = None
    answer: str
    language: str | None = None  # NEW: The language used for the response
    language_detected: bool = True
    extracted_text: str | None = None
    sources: list[SourceDTO] = Field(default_factory=list)
    maps: str | None = None
    should_escalate: bool = False
    needs_email_for_ticket: bool = False  # Same as should_escalate
    reason: str | None = None
    ticket_draft: TicketDraftDTO | None = None
