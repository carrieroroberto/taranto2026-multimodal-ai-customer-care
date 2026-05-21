from fastapi import APIRouter, status

from backend.app.schemas.feedback import FeedbackRequestDTO
from backend.app.repositories.persistence_repository import save_feedback


router = APIRouter(tags=["feedback"])


@router.post("/feedback", status_code=status.HTTP_201_CREATED)
def post_feedback(feedback: FeedbackRequestDTO):
    save_feedback(feedback.model_dump())
    return {"status": "ok", "message": "Feedback received"}
