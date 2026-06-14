from fastapi import APIRouter

from backend.app.api.chat import router as chat_router
from backend.app.api.conversations import router as conversations_router
from backend.app.api.health import router as health_router
from backend.app.api.feedback import router as feedback_router
from backend.app.api.tickets import router as tickets_router
from backend.app.api.kpis import router as kpis_router
from backend.app.api.knowledge import router as knowledge_router
from backend.app.api.operator import auth_router, router as operator_router

router = APIRouter()

router.include_router(health_router)
router.include_router(conversations_router)
router.include_router(chat_router)
router.include_router(feedback_router)
router.include_router(tickets_router)
router.include_router(kpis_router)
router.include_router(knowledge_router)
router.include_router(auth_router)
router.include_router(operator_router)
