from fastapi import APIRouter

from backend.app.api.chat import router as chat_router
from backend.app.api.health import router as health_router
from backend.app.api.feedback import router as feedback_router
from backend.app.api.tickets import router as tickets_router

router = APIRouter()

router.include_router(health_router)
router.include_router(chat_router)
router.include_router(feedback_router)
router.include_router(tickets_router)
