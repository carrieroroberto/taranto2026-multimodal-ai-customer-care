import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from backend.app.api.routes import router
from backend.app.services.errors import AppServiceError
from backend.app.services.rag_service import start_knowledge_base_startup_task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
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
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.exception_handler(AppServiceError)
async def app_service_error_handler(
    _request: Request,
    exc: AppServiceError,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )
