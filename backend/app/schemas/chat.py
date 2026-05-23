from pydantic import BaseModel, Field

from backend.app.schemas.ticket import TicketDraftDTO


class ChatRequestDTO(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = None
    visual_context: str | None = None
    planning_message: str | None = None
    language: str | None = None


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
    answer: str
    extracted_text: str | None = None
    sources: list[SourceDTO] = Field(default_factory=list)
    maps: str | None = None
    should_escalate: bool = False
    reason: str | None = None
    ticket_draft: TicketDraftDTO | None = None
