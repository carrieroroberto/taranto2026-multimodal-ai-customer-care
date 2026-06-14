import json
import re
import threading
import unicodedata
import uuid
from pathlib import Path
from typing import Any

from backend.app.config import settings
from backend.app.repositories import get_collection, load_jsonl
from backend.app.schemas.knowledge import KnowledgeRecordCreateDTO
from backend.app.services.errors import DependencyServiceError, ValidationServiceError
from backend.app.services.rag_service import embed_texts, mark_kb_ready, set_kb_status


ALLOWED_KNOWLEDGE_DOMAINS = [
    "general",
    "venue",
    "calendar",
    "ticketing",
    "accessibility",
    "volunteering",
]

ALLOWED_KNOWLEDGE_TYPES = [
    "custom_information",
    "faq",
    "venue",
    "event_schedule",
    "contacts",
    "ticketing",
    "volunteers",
    "accessibility",
    "transport",
    "institutional",
]

_KB_APPEND_LOCK = threading.Lock()


def build_knowledge_record(payload: KnowledgeRecordCreateDTO) -> dict[str, Any]:
    record_id = normalize_record_id(payload.record_id) if payload.record_id else generated_record_id(payload.title)
    metadata: dict[str, str | int | float | bool] = {
        "type": normalize_metadata_token(payload.item_type) or "custom_information",
        "title": payload.title.strip(),
        "source_url": payload.source_url.strip(),
        "domain": payload.domain,
    }

    if payload.address:
        metadata["address"] = payload.address.strip()
    if payload.latitude is not None:
        metadata["latitude"] = payload.latitude
    if payload.longitude is not None:
        metadata["longitude"] = payload.longitude

    for key, value in payload.metadata.items():
        normalized_key = normalize_metadata_key(key)
        if not normalized_key or value is None:
            continue
        if normalized_key in metadata:
            continue
        metadata[normalized_key] = value

    return {
        "id": record_id,
        "document": payload.document.strip(),
        "metadata": metadata,
    }


def append_and_index_knowledge_record(payload: KnowledgeRecordCreateDTO) -> tuple[dict[str, Any], int]:
    record = build_knowledge_record(payload)
    append_knowledge_record(record)
    collection_count = index_knowledge_record(record)
    return record, collection_count


def append_knowledge_record(record: dict[str, Any]) -> None:
    with _KB_APPEND_LOCK:
        records = load_jsonl(settings.kb_path)
        if any(existing["id"] == record["id"] for existing in records):
            raise ValidationServiceError(f"Knowledge record already exists: {record['id']}")

        kb_path = Path(settings.kb_path)
        kb_path.parent.mkdir(parents=True, exist_ok=True)
        with kb_path.open("ab+") as file:
            file.seek(0, 2)
            if file.tell() > 0:
                file.seek(-1, 2)
                if file.read(1) != b"\n":
                    file.write(b"\n")
            encoded = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            file.write(encoded + b"\n")


def index_knowledge_record(record: dict[str, Any]) -> int:
    try:
        set_kb_status("incremental_ingesting")
        collection = get_collection()
        collection.add(
            ids=[record["id"]],
            documents=[record["document"]],
            metadatas=[record["metadata"]],
            embeddings=embed_texts([record["document"]]),
        )
        mark_kb_ready("ok")
        return collection.count()
    except Exception as exc:
        set_kb_status("incremental_ingest_failed")
        raise DependencyServiceError(f"Knowledge record indexing failed: {exc}") from exc


def normalize_record_id(value: str) -> str:
    record_id = normalize_slug(value, separator="_")
    if not record_id or len(record_id) < 3:
        raise ValidationServiceError("Knowledge record id is invalid.")
    if len(record_id) > 140:
        raise ValidationServiceError("Knowledge record id is too long.")
    return record_id


def generated_record_id(title: str) -> str:
    slug = normalize_slug(title, separator="_")[:80] or "record"
    return f"custom_{slug}_{uuid.uuid4().hex[:8]}"


def normalize_metadata_token(value: str) -> str:
    return normalize_slug(value, separator="_")[:80]


def normalize_metadata_key(value: str) -> str:
    key = normalize_slug(value, separator="_")
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", key or ""):
        return ""
    return key


def normalize_slug(value: str, separator: str = "_") -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", separator, text)
    text = re.sub(f"{re.escape(separator)}+", separator, text)
    return text.strip(separator)
