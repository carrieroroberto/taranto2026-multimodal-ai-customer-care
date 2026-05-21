from pydantic import BaseModel


class HealthResponseDTO(BaseModel):
    status: str
    collection_name: str
    collection_count: int
    embedding_model: str
    llm_model: str
    kb_ready: bool
    kb_error: str | None = None
