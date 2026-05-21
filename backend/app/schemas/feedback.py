from pydantic import BaseModel, Field


class FeedbackRequestDTO(BaseModel):
    session_id: str | None = None
    message_id: str | None = None  # Optional if we want to tie feedback to a specific message
    rating: int = Field(..., ge=1, le=5)  # 1-5 or maybe just 1/0 for thumbs up/down
    comment: str | None = None
