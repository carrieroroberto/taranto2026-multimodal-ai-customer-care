from typing import Annotated

from fastapi import APIRouter, Depends, status

from backend.app.api.operator import get_current_operator
from backend.app.schemas.knowledge import (
    KnowledgeIngestResponseDTO,
    KnowledgeOptionsDTO,
    KnowledgeRecordCreateDTO,
    KnowledgeRecordDTO,
)
from backend.app.services.knowledge_service import (
    ALLOWED_KNOWLEDGE_DOMAINS,
    ALLOWED_KNOWLEDGE_TYPES,
    append_and_index_knowledge_record,
)


router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/options", response_model=KnowledgeOptionsDTO)
def knowledge_options(
    _current_operator: Annotated[dict, Depends(get_current_operator)],
) -> KnowledgeOptionsDTO:
    return KnowledgeOptionsDTO(
        domains=ALLOWED_KNOWLEDGE_DOMAINS,
        item_types=ALLOWED_KNOWLEDGE_TYPES,
    )


@router.post("/records", status_code=status.HTTP_201_CREATED, response_model=KnowledgeIngestResponseDTO)
def create_knowledge_record(
    payload: KnowledgeRecordCreateDTO,
    _current_operator: Annotated[dict, Depends(get_current_operator)],
) -> KnowledgeIngestResponseDTO:
    record, collection_count = append_and_index_knowledge_record(payload)
    return KnowledgeIngestResponseDTO(
        status="completed",
        message="Record aggiunto e indicizzato nella knowledge base.",
        record=KnowledgeRecordDTO(**record),
        collection_count=collection_count,
    )
