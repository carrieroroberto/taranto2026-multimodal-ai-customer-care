from fastapi import APIRouter, HTTPException, status

from backend.app.schemas.feedback import FeedbackRequestDTO, MessageFeedbackPatchDTO
from backend.app.repositories.persistence_repository import save_feedback, update_message_satisfaction


router = APIRouter(tags=["feedback"])


@router.post("/feedback", status_code=status.HTTP_201_CREATED)
def post_feedback(feedback: FeedbackRequestDTO):
    try:
        updated = save_feedback(feedback.model_dump())
        if not updated:
            raise HTTPException(status_code=404, detail="Bot message not found.")
        return {"status": "ok", "message": "Feedback received"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/messages/{message_id}/feedback")
def patch_message_feedback(message_id: str, feedback: MessageFeedbackPatchDTO):
    try:
        updated = update_message_satisfaction(message_id, feedback.satisfaction)
        if not updated:
            raise HTTPException(status_code=404, detail="Message not found.")
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
