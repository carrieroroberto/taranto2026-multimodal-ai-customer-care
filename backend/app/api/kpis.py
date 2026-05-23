from fastapi import APIRouter

from backend.app.repositories.persistence_repository import get_kpi_summary
from backend.app.schemas.kpi import KpiSummaryDTO


router = APIRouter(tags=["kpis"])


@router.get("/kpis", response_model=KpiSummaryDTO)
def kpis() -> KpiSummaryDTO:
    return KpiSummaryDTO(**get_kpi_summary())
