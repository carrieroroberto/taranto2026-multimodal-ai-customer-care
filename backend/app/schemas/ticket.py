from typing import Literal

from pydantic import BaseModel


TicketCategory = Literal[
    "ticketing",
    "venue_information",
    "accessibility",
    "volunteering",
    "partnership",
    "school_project",
    "calendar",
    "transport",
    "complaint",
    "general_information",
    "unknown",
]

TicketPriority = Literal["low", "medium", "high"]


class TicketDraftDTO(BaseModel):
    category: TicketCategory
    summary: str
    user_message: str
    retrieved_context_summary: str
    priority: TicketPriority


class TicketRequestDTO(BaseModel):
    conversation_id: str
    user_email: str
    session_id: str | None = None
    category: TicketCategory | None = None
    domain: str | None = None
    summary: str | None = None
    user_message: str | None = None
    original_message: str | None = None
    translated_message: str | None = None
    priority: TicketPriority | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
