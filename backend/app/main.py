import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes import router
from backend.app.config import settings
from backend.app.repositories.database import init_database
from backend.app.repositories.persistence_repository import ensure_default_operator
from backend.app.services.auth_service import get_password_hash
from backend.app.services.errors import AppServiceError
from backend.app.services.rag_service import start_knowledge_base_startup_task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "../data/uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_database()
    
    # Seed default operator
    if settings.default_operator_email and settings.default_operator_password:
        logger.info("Seeding default operator: %s", settings.default_operator_email)
        hashed_password = get_password_hash(settings.default_operator_password)
        ensure_default_operator(settings.default_operator_email, hashed_password)

    start_knowledge_base_startup_task()
    yield


app = FastAPI(
    title="Taranto 2026 Chatbot Backend",
    version="0.1.0",
    description="RAG API for the Taranto 2026 chatbot.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"https://.*\.trycloudflare\.com",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(router, prefix="/api")

app.mount("/api/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

@app.exception_handler(AppServiceError)
async def app_service_error_handler(
    _request: Request,
    exc: AppServiceError,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )
