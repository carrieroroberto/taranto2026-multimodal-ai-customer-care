import json
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings as ChromaSettings

from backend.app.config import settings


REQUIRED_FIELDS = {"id", "document", "metadata"}
ALLOWED_METADATA_TYPES = (str, int, float, bool)


def collection_metadata() -> dict[str, str]:
    return {
        "hnsw:space": "cosine",
        "embedding_model": settings.embedding_model,
    }


def load_jsonl(path: str | Path = settings.kb_path) -> list[dict[str, Any]]:
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"KB not found: {path}")

    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at line {line_number}: {exc}") from exc

            validate_record(record, line_number, seen_ids)
            records.append(record)

    return records


def validate_record(
    record: dict[str, Any],
    line_number: int,
    seen_ids: set[str],
) -> None:
    missing = REQUIRED_FIELDS - set(record.keys())
    if missing:
        raise ValueError(f"Line {line_number}: missing fields {sorted(missing)}")

    record_id = record["id"]
    document = record["document"]
    metadata = record["metadata"]

    if not isinstance(record_id, str) or not record_id.strip():
        raise ValueError(f"Line {line_number}: invalid id")

    if record_id in seen_ids:
        raise ValueError(f"Line {line_number}: duplicated id {record_id}")
    seen_ids.add(record_id)

    if not isinstance(document, str) or not document.strip():
        raise ValueError(f"Line {line_number}: empty or invalid document")

    if not isinstance(metadata, dict):
        raise ValueError(f"Line {line_number}: metadata must be an object")

    for key, value in metadata.items():
        if value is None:
            raise ValueError(f"Line {line_number}: metadata.{key} is null")
        if not isinstance(value, ALLOWED_METADATA_TYPES):
            raise ValueError(
                f"Line {line_number}: metadata.{key} has unsupported type "
                f"{type(value).__name__}"
            )


def get_chroma_client() -> chromadb.HttpClient:
    return chromadb.HttpClient(
        host=settings.chroma_host,
        port=settings.chroma_port,
        settings=ChromaSettings(
            anonymized_telemetry=False,
            chroma_product_telemetry_impl="backend.app.services.rag_service.NoopTelemetry",
            chroma_telemetry_impl="backend.app.services.rag_service.NoopTelemetry",
        ),
    )


def get_collection() -> Collection:
    return get_chroma_client().get_or_create_collection(
        name=settings.collection_name,
        metadata=collection_metadata(),
    )


def recreate_collection() -> Collection:
    client = get_chroma_client()

    try:
        client.delete_collection(settings.collection_name)
    except Exception:
        pass

    return client.get_or_create_collection(
        name=settings.collection_name,
        metadata=collection_metadata(),
    )
