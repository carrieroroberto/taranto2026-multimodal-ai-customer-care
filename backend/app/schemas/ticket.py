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
    session_id: str | None = None
    category: TicketCategory
    summary: str
    user_message: str
    priority: TicketPriority
    contact_email: str | None = None
    contact_phone: str | None = None
