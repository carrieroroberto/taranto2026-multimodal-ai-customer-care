from fastapi import APIRouter

from backend.app.schemas import HealthResponseDTO
from backend.app.services.rag_service import get_health


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponseDTO)
def health() -> HealthResponseDTO:
    return get_health()
