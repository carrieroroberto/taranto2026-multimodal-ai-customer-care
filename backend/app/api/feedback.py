from fastapi import APIRouter, HTTPException, status

from backend.app.schemas.feedback import FeedbackRequestDTO
from backend.app.repositories.persistence_repository import save_feedback


router = APIRouter(tags=["feedback"])


@router.post("/feedback", status_code=status.HTTP_201_CREATED)
def post_feedback(feedback: FeedbackRequestDTO):
    updated = save_feedback(feedback.model_dump())
    if not updated:
        raise HTTPException(status_code=404, detail="Bot message not found.")
    return {"status": "ok", "message": "Feedback received"}
