import logging
import re
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any
from urllib.parse import quote

from chromadb.api.models.Collection import Collection
from chromadb.telemetry.product import ProductTelemetryClient, ProductTelemetryEvent
from overrides import override
from sentence_transformers import SentenceTransformer

from backend.app.config import settings
from backend.app.repositories import get_collection, load_jsonl, recreate_collection
from backend.app.schemas import (
    HealthResponseDTO,
)
from backend.app.services.errors import DependencyServiceError, ValidationServiceError


logger = logging.getLogger(__name__)

KB_TOTAL_RECORDS = 2557
TICKETING_RECORD_ID = "ticketing_general_taranto_2026"
FILTERED_RETRIEVAL_MIN_RESULTS = 3
MAX_ANSWER_CONTEXTS = 8

_KB_READY = False
_KB_STATUS = "not_started"
_KB_ERROR: str | None = None


class NoopTelemetry(ProductTelemetryClient):
    @override
    def capture(self, event: ProductTelemetryEvent) -> None:
        return None


@dataclass(frozen=True)
class PlannedRetrievalQuery:
    query: str
    domain: str | None = None
    weight: float = 1.0


@dataclass(frozen=True)
class QueryPlan:
    original_query: str
    retrieval_query: str
    response_language: str
    domain: str
    filters: list[str]
    expanded_queries: list[str]
    intent: str = "unknown"
    domains: list[str] = field(default_factory=lambda: ["general"])
    entities: dict[str, str | None] = field(default_factory=dict)
    retrieval_queries: list[PlannedRetrievalQuery] = field(default_factory=list)
    needs_clarification: bool = False
    clarification_question: str | None = None


@dataclass
class RetrievalCandidate:
    item_id: str
    document: str
    metadata: dict[str, Any]
    distance: float | None = None
    score: float = 0.0
    query_domains: set[str] = field(default_factory=set)
    query_weights: list[float] = field(default_factory=list)
    matched_queries: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class RetrievedContext:
    item_id: str
    title: str | None
    item_type: str | None
    source_url: str | None
    address: str | None
    latitude: float | None
    longitude: float | None
    maps_url: str | None
    document: str


@dataclass(frozen=True)
class CalendarFact:
    discipline: str | None
    place: str
    schedule: str


def set_kb_status(status: str) -> None:
    global _KB_STATUS
    _KB_STATUS = status


def mark_kb_ready(status: str = "ok") -> None:
    global _KB_READY, _KB_STATUS, _KB_ERROR
    _KB_READY = True
    _KB_STATUS = status
    _KB_ERROR = None


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(settings.embedding_model)


def embed_texts(texts: list[str]) -> list[list[float]]:
    vectors = get_embedding_model().encode(
        texts,
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return vectors.tolist()


def start_knowledge_base_startup_task() -> None:
    if not settings.auto_ingest_on_startup:
        mark_kb_ready("disabled")
        return

    thread = threading.Thread(target=ensure_knowledge_base, daemon=True)
    thread.start()


def ensure_knowledge_base() -> None:
    if not settings.auto_ingest_on_startup:
        mark_kb_ready("disabled")
        return

    global _KB_ERROR
    last_error: Exception | None = None

    for attempt in range(1, 31):
        try:
            set_kb_status("checking")
            records = load_jsonl(settings.kb_path)
            collection = get_collection()
            count = collection.count()
            metadata = getattr(collection, "metadata", None) or {}
            stored_embedding_model = metadata.get("embedding_model")
            needs_ingest = (
                settings.force_reingest_on_startup
                or count == 0
                or count != len(records)
                or stored_embedding_model != settings.embedding_model
            )

            if needs_ingest:
                reason = ingest_reason(count, len(records), stored_embedding_model)
                set_kb_status(f"ingesting:{reason}")
                logger.info("kb_ingest_start reason=%s count=%s", reason, count)
                ingest_knowledge_base(records)
                logger.info("kb_ingest_completed")

            mark_kb_ready("ok")
            return
        except Exception as exc:
            last_error = exc
            _KB_ERROR = str(exc)
            logger.warning("kb_startup_check_failed attempt=%s error=%s", attempt, exc)
            time.sleep(2)

    set_kb_status("error")
    raise DependencyServiceError(f"Knowledge base startup ingest failed: {last_error}")


def ingest_reason(
    count: int,
    expected_count: int,
    stored_embedding_model: str | None,
) -> str:
    if settings.force_reingest_on_startup:
        return "forced"
    if count == 0:
        return "empty_collection"
    if count != expected_count:
        return "partial_or_stale_collection"
    if stored_embedding_model != settings.embedding_model:
        return "embedding_model_changed"
    return "unknown"


def ingest_knowledge_base(records: list[dict[str, Any]] | None = None) -> int:
    try:
        if records is None:
            records = load_jsonl(settings.kb_path)

        collection = recreate_collection()
        for start in range(0, len(records), settings.ingest_batch_size):
            batch = records[start : start + settings.ingest_batch_size]
            documents = [record["document"] for record in batch]
            collection.add(
                ids=[record["id"] for record in batch],
                documents=documents,
                metadatas=[record["metadata"] for record in batch],
                embeddings=embed_texts(documents),
            )
            logger.info(
                "kb_ingest_progress inserted=%s total=%s",
                min(start + settings.ingest_batch_size, len(records)),
                len(records),
            )

        return collection.count()
    except (FileNotFoundError, ValueError) as exc:
        raise ValidationServiceError(f"Knowledge base invalid: {exc}") from exc
    except Exception as exc:
        raise DependencyServiceError(f"Knowledge base ingest unavailable: {exc}") from exc


def get_health() -> HealthResponseDTO:
    try:
        collection = get_collection()
        count = collection.count()
    except Exception as exc:
        raise DependencyServiceError(f"Chroma unavailable: {exc}") from exc

    return HealthResponseDTO(
        status=_KB_STATUS if settings.auto_ingest_on_startup else "ok",
        collection_name=settings.collection_name,
        collection_count=count,
        embedding_model=settings.embedding_model,
        llm_model=settings.ollama_model,
        kb_ready=_KB_READY,
        kb_error=_KB_ERROR,
    )


def ensure_knowledge_base_ready() -> None:
    if not _KB_READY:
        raise DependencyServiceError(
            f"Knowledge base is not ready yet. Current status: {_KB_STATUS}"
        )


def retrieve_context(plan: QueryPlan, n_results: int) -> list[RetrievalCandidate]:
    ensure_knowledge_base_ready()
    collection = get_collection()
    return retrieve_ranked(collection, plan, n_results)


def asks_ticketing_info(plan: QueryPlan) -> bool:
    return (
        plan.domain == "ticketing"
        or "ticketing" in plan.domains
        or plan.intent == "ticketing"
        or any(query.domain == "ticketing" for query in plan.retrieval_queries)
    )


def retrieve_ranked(
    collection: Collection,
    plan: QueryPlan,
    n_results: int,
) -> list[RetrievalCandidate]:
    retrieval_queries = planned_retrieval_queries(plan)
    query_embeddings = embed_texts([query.query for query in retrieval_queries])
    candidates: dict[str, RetrievalCandidate] = {}

    for retrieval_query, query_embedding in zip(retrieval_queries, query_embeddings):
        query_candidates: dict[str, RetrievalCandidate] = {}

        if retrieval_query.domain and retrieval_query.domain != "general":
            query_candidates.update(
                vector_candidates(
                    collection,
                    query_embedding,
                    n_results,
                    retrieval_query,
                    metadata_filter={"domain": retrieval_query.domain},
                )
            )

        if (
            not retrieval_query.domain
            or retrieval_query.domain == "general"
            or len(query_candidates) < FILTERED_RETRIEVAL_MIN_RESULTS
        ):
            query_candidates.update(
                vector_candidates(
                    collection,
                    query_embedding,
                    n_results,
                    retrieval_query,
                    metadata_filter=None,
                )
            )

        for item_id, candidate in query_candidates.items():
            register_retrieval_match(candidate, retrieval_query)
            merge_candidate(candidates, item_id, candidate)

    force_include_records(collection, plan, candidates)

    for candidate in candidates.values():
        candidate.score = score_candidate(plan, candidate)

    ranked = sorted(
        candidates.values(),
        key=lambda candidate: (
            candidate.score,
            -(candidate.distance if candidate.distance is not None else 2.0),
            candidate.item_id,
        ),
        reverse=True,
    )[:n_results]
    fill_missing_distances(collection, query_embeddings[0], ranked)

    logger.info(
        "rag_retrieve query=%r intent=%s domains=%s retrieval_queries=%s result_ids=%s scores=%s",
        plan.original_query,
        plan.intent,
        plan.domains,
        [(query.query, query.domain, query.weight) for query in retrieval_queries],
        [candidate.item_id for candidate in ranked],
        [round(candidate.score, 3) for candidate in ranked],
    )
    return ranked


def planned_retrieval_queries(plan: QueryPlan) -> list[PlannedRetrievalQuery]:
    if plan.retrieval_queries:
        queries = [query for query in plan.retrieval_queries if query.query.strip()]
    else:
        queries = [
            PlannedRetrievalQuery(query=query, domain=plan.domain, weight=1.0)
            for query in [plan.retrieval_query, *plan.expanded_queries]
            if query.strip()
        ]
    
    # Always include a high-level general query for general intents to ensure sources are found
    if plan.intent in {"general_information", "participation"} or not queries:
        queries.append(PlannedRetrievalQuery(query="Giochi del Mediterraneo Taranto 2026 informazioni generali", domain="general", weight=0.8))

    return deduplicate_planned_queries(queries) or [
        PlannedRetrievalQuery(query=plan.original_query, domain=None, weight=1.0)
    ]


def deduplicate_planned_queries(
    queries: list[PlannedRetrievalQuery],
) -> list[PlannedRetrievalQuery]:
    deduplicated: list[PlannedRetrievalQuery] = []
    seen: set[tuple[str, str | None]] = set()
    for query in queries:
        key = (normalize_text(query.query), query.domain)
        if not key[0] or key in seen:
            continue
        deduplicated.append(query)
        seen.add(key)
    return deduplicated[:4]


def merge_candidate(
    candidates: dict[str, RetrievalCandidate],
    item_id: str,
    candidate: RetrievalCandidate,
) -> None:
    existing = candidates.get(item_id)
    if existing is None:
        candidates[item_id] = candidate
        return

    if candidate.distance is not None and (
        existing.distance is None or candidate.distance < existing.distance
    ):
        existing.distance = candidate.distance
    existing.query_domains.update(candidate.query_domains)
    existing.query_weights.extend(candidate.query_weights)
    existing.matched_queries.update(candidate.matched_queries)


def register_retrieval_match(
    candidate: RetrievalCandidate,
    retrieval_query: PlannedRetrievalQuery,
) -> None:
    if retrieval_query.domain:
        candidate.query_domains.add(retrieval_query.domain)
    candidate.query_weights.append(retrieval_query.weight)
    candidate.matched_queries.add(retrieval_query.query)


def select_answer_candidates(
    candidates: list[RetrievalCandidate],
    plan: QueryPlan,
) -> list[RetrievalCandidate]:
    if not candidates:
        return []

    top_score = candidates[0].score
    score_floor = max(0.05, top_score - 0.45)
    selected: list[RetrievalCandidate] = []

    for candidate in candidates:
        if len(selected) >= MAX_ANSWER_CONTEXTS:
            break
        if selected and candidate.score < score_floor:
            continue
        selected.append(candidate)

    return selected or candidates[:1]


def candidate_relevant_to_plan(
    candidate: RetrievalCandidate,
    plan: QueryPlan,
) -> bool:
    return True


def candidate_type(candidate: RetrievalCandidate) -> str:
    return normalize_text(candidate.metadata.get("type", "")).replace(" ", "_")


def vector_candidates(
    collection: Collection,
    query_embedding: list[float],
    n_results: int,
    retrieval_query: PlannedRetrievalQuery,
    metadata_filter: dict[str, Any] | None = None,
) -> dict[str, RetrievalCandidate]:
    count = collection.count()
    if count == 0:
        return {}

    raw_results = min(count, max(n_results * 6, 32))
    query_kwargs: dict[str, Any] = {
        "query_embeddings": [query_embedding],
        "n_results": raw_results,
        "include": ["documents", "metadatas", "distances"],
    }
    if metadata_filter:
        query_kwargs["where"] = metadata_filter

    try:
        result = collection.query(**query_kwargs)
    except Exception as exc:
        if metadata_filter:
            logger.debug(
                "rag_domain_filter_skipped domain=%s error=%s",
                retrieval_query.domain,
                exc,
            )
            return {}
        raise

    candidates: dict[str, RetrievalCandidate] = {}
    for item_id, document, metadata, distance in zip(
        result["ids"][0],
        result["documents"][0],
        result["metadatas"][0],
        result["distances"][0],
    ):
        candidates[item_id] = RetrievalCandidate(
            item_id=item_id,
            document=document,
            metadata=metadata,
            distance=float(distance),
        )
    return candidates


def force_include_records(
    collection: Collection,
    plan: QueryPlan,
    candidates: dict[str, RetrievalCandidate],
) -> None:
    ids: list[str] = []
    if asks_ticketing_info(plan):
        ids.append(TICKETING_RECORD_ID)

    missing_ids = [item_id for item_id in ids if item_id not in candidates]
    if not missing_ids:
        return

    result = collection.get(ids=missing_ids, include=["documents", "metadatas"])
    for item_id, document, metadata in zip(
        result.get("ids", []),
        result.get("documents", []),
        result.get("metadatas", []),
    ):
        candidate = RetrievalCandidate(
            item_id=item_id,
            document=document,
            metadata=metadata,
        )
        candidate.query_domains.add("ticketing")
        candidate.query_weights.append(1.0)
        candidates[item_id] = candidate


def score_candidate(plan: QueryPlan, candidate: RetrievalCandidate) -> float:
    text = searchable_text(candidate)
    item_type = candidate_type(candidate)

    score = embedding_score(candidate)
    if candidate.query_weights:
        score *= max(candidate.query_weights)

    if domain_matches_candidate(plan, candidate):
        score += 0.10

    entity_matches = matched_entity_count(plan, text)
    score += 0.05 * entity_matches

    if intent_matches_candidate(plan, item_type, text):
        score += 0.05

    if asks_ticketing_info(plan) and candidate.item_id == TICKETING_RECORD_ID:
        score += 0.15

    if entity_terms(plan) and entity_matches == 0 and looks_generic(candidate):
        score -= 0.05

    return score


def embedding_score(candidate: RetrievalCandidate) -> float:
    if candidate.distance is None:
        return 0.15
    return max(0.0, 1.0 - min(candidate.distance, 1.0))


def domain_matches_candidate(plan: QueryPlan, candidate: RetrievalCandidate) -> bool:
    candidate_domain = normalize_text(candidate.metadata.get("domain", "")).replace(" ", "_")
    item_type = candidate_type(candidate)
    domains = {
        domain
        for domain in [plan.domain, *plan.domains, *candidate.query_domains]
        if domain and domain != "general"
    }
    if candidate_domain and candidate_domain in domains:
        return True
    return any(domain in item_type or item_type in domain for domain in domains)


def intent_matches_candidate(plan: QueryPlan, item_type: str, text: str) -> bool:
    intent = normalize_text(plan.intent).replace(" ", "_")
    return bool(
        intent
        and intent != "unknown"
        and (intent in item_type or item_type in intent or intent in text)
    )


def matched_entity_count(plan: QueryPlan, text: str) -> int:
    return sum(1 for term in entity_terms(plan) if term_matches_text(term, text))


def entity_terms(plan: QueryPlan) -> list[str]:
    terms: list[str] = []
    for value in [*plan.filters, *plan.entities.values()]:
        if value is None:
            continue
        normalized = normalize_text(value)
        if normalized and normalized not in terms:
            terms.append(normalized)
    return terms


def looks_generic(candidate: RetrievalCandidate) -> bool:
    item_type = candidate_type(candidate)
    title = normalize_text(candidate.metadata.get("title", ""))
    return contains_any(item_type, ("general", "overview", "catalog")) or contains_any(
        title,
        ("overview", "panoramica", "catalogo"),
    )


def fill_missing_distances(
    collection: Collection,
    query_embedding: list[float],
    candidates: list[RetrievalCandidate],
) -> None:
    missing = [candidate for candidate in candidates if candidate.distance is None]
    if not missing:
        return

    result = collection.get(
        ids=[candidate.item_id for candidate in missing],
        include=["embeddings"],
    )
    embeddings_by_id = dict(zip(result["ids"], result["embeddings"]))
    for candidate in missing:
        embedding = embeddings_by_id.get(candidate.item_id)
        if embedding is not None:
            candidate.distance = cosine_distance(query_embedding, embedding)


def cosine_distance(first: list[float], second: Any) -> float:
    second_values = list(second)
    dot = sum(a * b for a, b in zip(first, second_values))
    first_norm = sum(a * a for a in first) ** 0.5
    second_norm = sum(b * b for b in second_values) ** 0.5
    if first_norm == 0 or second_norm == 0:
        return 1.0
    return 1.0 - (dot / (first_norm * second_norm))


def to_context(candidate: RetrievalCandidate) -> RetrievedContext:
    metadata = candidate.metadata
    latitude = as_optional_float(metadata.get("latitude"))
    longitude = as_optional_float(metadata.get("longitude"))
    maps_url = None
    if latitude is not None and longitude is not None:
        maps_url = google_maps_url(latitude, longitude)

    return RetrievedContext(
        item_id=candidate.item_id,
        title=as_optional_string(metadata.get("title")),
        item_type=as_optional_string(metadata.get("type")),
        source_url=as_optional_string(metadata.get("source_url")),
        address=as_optional_string(metadata.get("address")),
        latitude=latitude,
        longitude=longitude,
        maps_url=maps_url,
        document=candidate.document,
    )


def meaningful_terms(plan: QueryPlan) -> set[str]:
    return {term for term in entity_terms(plan) if len(term) > 2}


def normalize_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = text.replace("\u2019", "'").replace("`", "'")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def searchable_text(candidate: RetrievalCandidate) -> str:
    metadata = candidate.metadata
    parts = [
        candidate.item_id,
        metadata.get("title", ""),
        metadata.get("type", ""),
        metadata.get("address", ""),
        candidate.document,
    ]
    return normalize_text(" ".join(str(part) for part in parts if part is not None))


def term_matches_text(term: str, text: str, allow_fuzzy: bool = True) -> bool:
    if term in text:
        return True
    if not allow_fuzzy or len(term) < 7:
        return False

    for token in set(text.split()):
        if not token or token[0] != term[0]:
            continue
        if abs(len(token) - len(term)) > 2:
            continue
        if SequenceMatcher(None, term, token).ratio() >= 0.84:
            return True
    return False


def contains_any(haystack: str, terms: tuple[str, ...]) -> bool:
    return any(term in haystack for term in terms)


def as_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def as_optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def google_maps_url(latitude: float, longitude: float) -> str:
    # Round to 5 decimal places to normalize slightly different coordinates for same venue
    lat = round(latitude, 5)
    lon = round(longitude, 5)
    query = quote(f"{lat},{lon}")
    return f"https://www.google.com/maps/search/?api=1&query={query}"


def parse_retrieval_queries(
    queries: list[dict[str, Any]] | None,
    original_message: str,
    default_domains: list[str],
) -> list[PlannedRetrievalQuery]:
    if not queries:
        return [PlannedRetrievalQuery(query=original_message, domain=default_domains[0])]

    result: list[PlannedRetrievalQuery] = []
    for q in queries:
        text = str(q.get("query") or "").strip()
        if not text:
            continue
        domain = q.get("domain")
        weight = float(q.get("weight") or 1.0)
        result.append(PlannedRetrievalQuery(query=text, domain=domain, weight=weight))
    
    return result or [PlannedRetrievalQuery(query=original_message, domain=default_domains[0])]


def translate_static_answer(text: str, target_lang: str) -> str:
    # This is a stub for a real translation service or predefined translations
    # For now, we just return the text as is if it's already in the target language
    # or if it's a demo. In a real app, this would use a translation API.
    return text
