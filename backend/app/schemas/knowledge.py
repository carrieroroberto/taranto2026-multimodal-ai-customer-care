from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


KnowledgeDomain = Literal[
    "general",
    "venue",
    "calendar",
    "ticketing",
    "accessibility",
    "volunteering",
]


class KnowledgeRecordCreateDTO(BaseModel):
    record_id: str | None = Field(default=None, max_length=140)
    title: str = Field(..., min_length=3, max_length=180)
    item_type: str = Field(default="custom_information", min_length=2, max_length=80)
    domain: KnowledgeDomain = "general"
    source_url: str = Field(default="https://www.ta2026.com/", min_length=8, max_length=500)
    document: str = Field(..., min_length=40, max_length=12000)
    address: str | None = Field(default=None, max_length=300)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)

    @field_validator("record_id", "title", "item_type", "domain", "source_url", "document", "address", mode="before")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(value).strip()


class KnowledgeRecordDTO(BaseModel):
    id: str
    document: str
    metadata: dict[str, Any]


class KnowledgeIngestResponseDTO(BaseModel):
    status: str
    message: str
    record: KnowledgeRecordDTO
    collection_count: int | None = None


class KnowledgeOptionsDTO(BaseModel):
    domains: list[str]
    item_types: list[str]
