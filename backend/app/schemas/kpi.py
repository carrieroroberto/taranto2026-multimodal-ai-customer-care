from pydantic import BaseModel


class KpiSummaryDTO(BaseModel):
    total_conversations: int
    total_messages: int
    user_messages: int
    bot_messages: int
    total_tickets: int
    open_tickets: int
    in_progress_tickets: int
    closed_tickets: int
    positive_feedback: int
    negative_feedback: int
    rated_messages: int
    satisfaction_rate: float | None = None
