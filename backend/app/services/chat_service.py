import logging
import re
import time
import uuid
from functools import lru_cache
from typing import Any
from urllib.parse import urlparse

from backend.app.config import settings
from backend.app.repositories.rag_repository import load_jsonl
from backend.app.schemas import ChatRequestDTO, ChatResponseDTO, SourceDTO, TicketDraftDTO
from backend.app.repositories.persistence_repository import (
    ensure_conversation,
    get_session_history,
    save_bot_message,
    save_user_message,
)
from backend.app.services.llm_service import (
    build_answer,
    build_query_plan,
    contains_any,
    detect_message_language,
    explicit_operator_requested,
    fallback_query_plan,
    human_operator_answer,
    is_refusal_answer,
    normalize_language_code,
    normalize_text,
    unavailable_answer,
)
from backend.app.services.errors import DependencyServiceError
from backend.app.services.rag_service import (
    QueryPlan,
    RetrievalCandidate,
    RetrievedContext,
    google_maps_url,
    retrieve_context,
    select_answer_candidates,
    to_context,
)


logger = logging.getLogger(__name__)


MAP_REQUEST_TERMS = (
    "dove",
    "mappa",
    "maps",
    "indirizzo",
    "come arrivare",
    "raggiungere",
    "si trova",
    "si svolge",
    "si gioca",
)
MOBILITY_REQUEST_TERMS = (
    "kyma",
    "mobilita",
    "mobility",
    "trasporto",
    "trasporti",
    "transport",
    "pullman",
    "autobus",
    "bus",
    "navetta",
    "shuttle",
    "fermata",
    "fermate",
    "linea",
    "linee",
    "come arrivare",
    "arrivare",
    "arriva",
    "arrivo",
    "raggiungere",
    "raggiungo",
    "parcheggio",
)
HUMAN_OPERATOR_TERMS = (
    "operatore",
    "persona",
    "umano",
    "assistenza",
    "contattare qualcuno",
    "parlare con",
)
URGENT_TERMS = ("urgente", "emergenza", "pericolo", "soccorso", "sicurezza")
LIVE_DATA_TERMS = ("live", "in tempo reale", "risultato adesso", "risultati live")
OFFICIAL_VERIFICATION_TERMS = (
    "conferma ufficiale",
    "verifica ufficiale",
    "mi confermi ufficialmente",
)
COMPLAINT_TERMS = ("reclamo", "lamentela", "segnalazione", "oggetto smarrito")
USELESS_REQUEST_TERMS = (
    "test",
    "prova",
    "asdf",
    "qwerty",
    "ciao",
    "salve",
    "ok",
    "grazie",
    "boh",
    "niente",
)
EVENT_RELATED_TERMS = (
    "giochi",
    "mediterraneo",
    "taranto",
    "tara",
    "stadio",
    "palazzetto",
    "pala",
    "sport",
    "gara",
    "evento",
    "atleta",
    "biglietto",
    "ticket",
    "volontari",
    "venue",
    "sede",
    "kyma",
    "bus",
    "pullman",
    "fermata",
    "parcheggio",
    "iacovone",
)

def answer_chat(request: ChatRequestDTO) -> ChatResponseDTO:
    started_at = time.perf_counter()
    message = normalize_required_message(request.message)
    session_id = request.session_id or str(uuid.uuid4())
    conversation_id = ensure_conversation(session_id=session_id)

    # Load history
    history = get_session_history(session_id)
    user_message_row = save_user_message(
        session_id,
        request.stored_user_content or message,
        request.message_type,
    )
    planning_message = request.planning_message if request.planning_message else message
    ui_lang = normalize_language_code(request.language) if request.language else "it"
    response_lang = detect_message_language(
        planning_message,
        ui_lang,
    )

    if explicit_operator_requested(message):
        import dataclasses

        plan = dataclasses.replace(
            fallback_query_plan(planning_message),
            response_language=response_lang,
        )
        answer = human_operator_answer(plan.response_language)
        bot_message_row = save_bot_message(session_id, answer)
        return ChatResponseDTO(
            session_id=session_id,
            conversation_id=conversation_id,
            user_message_id=user_message_row["id"],
            bot_message_id=bot_message_row["id"],
            message_id=bot_message_row["id"],
            answer=answer,
            language=plan.response_language,
            sources=[],
            maps=None,
            should_escalate=True,
            needs_email_for_ticket=True,
            reason="human_operator_requested",
            ticket_draft=build_ticket_draft(message, plan, "human_operator_requested", []),
        )

    if settings.ai_disabled:
        answer = ai_disabled_answer(request.language)
        bot_message_row = save_bot_message(session_id, answer)
        return ChatResponseDTO(
            session_id=session_id,
            conversation_id=conversation_id,
            user_message_id=user_message_row["id"],
            bot_message_id=bot_message_row["id"],
            answer=answer,
            sources=[],
            maps=None,
            should_escalate=False,
            reason="ai_disabled",
            ticket_draft=None,
        )

    plan = build_query_plan(planning_message, history)
    
    # The latest user message wins when its language can be detected; the UI value is only a fallback.
    final_lang = response_lang
    
    import dataclasses
    plan = dataclasses.replace(plan, response_language=final_lang)
    
    if request.visual_context:
        from backend.app.services.rag_service import PlannedRetrievalQuery
        
        anchored_context = f"{request.visual_context} Giochi del Mediterraneo Taranto 2026 logo emblema mascotte icmg"
        
        new_queries = list(plan.retrieval_queries) + [
            PlannedRetrievalQuery(query=anchored_context, domain="general", weight=1.5),
            PlannedRetrievalQuery(query=request.visual_context, domain="general", weight=1.0)
        ]
        new_expanded = list(plan.expanded_queries) + [request.visual_context, anchored_context]
        plan = dataclasses.replace(plan, retrieval_queries=new_queries, expanded_queries=new_expanded)

    if is_mobility_request(planning_message):
        from backend.app.services.rag_service import PlannedRetrievalQuery

        mobility_query = (
            f"{planning_message} trasporti pubblici fermata bus linee pullman "
            "indirizzo parcheggio venue_geocoding Taranto 2026"
        )
        new_queries = [
            PlannedRetrievalQuery(query=mobility_query, domain="venue", weight=1.8),
            PlannedRetrievalQuery(query=planning_message, domain="venue", weight=1.4),
            *list(plan.retrieval_queries),
        ]
        domains = ["venue", *[domain for domain in plan.domains if domain != "venue"]]
        plan = dataclasses.replace(
            plan,
            domain="venue",
            domains=domains,
            retrieval_queries=new_queries,
            expanded_queries=[mobility_query, *list(plan.expanded_queries)],
        )

    candidates = retrieve_context(plan, settings.n_results)
    answer_candidates = select_answer_candidates(candidates, plan)
    contexts = [to_context(candidate) for candidate in answer_candidates]
    if is_mobility_request(planning_message):
        contexts = ensure_mobility_context(planning_message, contexts)
    
    should_escalate, reason = escalation_decision(plan, contexts, candidates)

    try:
        answer = build_answer(message, plan, contexts, should_escalate, reason, history)
    except DependencyServiceError as exc:
        logger.warning("answer_generation_fallback language=%s error=%s", plan.response_language, exc)
        answer = unavailable_answer(plan.response_language)
        should_escalate = True
        reason = "llm_unavailable"

    # IMMEDIATE ESCALATION: If the bot refuses to answer or doesn't know, trigger escalation right away
    if is_refusal_answer(answer):
        logger.info("Refusal detected, triggering immediate escalation. Answer: %r", answer[:50])
        # Switch to the official fallback message if not already using it
        answer = unavailable_answer(plan.response_language)
        should_escalate = True
        reason = "immediate_refusal"

    # Only provide sources if we actually have context AND the answer is not a refusal/fallback.
    is_refusal = is_refusal_answer(answer)
    
    sources = []
    if contexts and not is_refusal:
        sources = build_sources(contexts, plan)
    
    # Logic for Maps based on what is ACTUALLY mentioned in the answer text:
    mentioned_maps = []
    norm_ans = normalize_text(answer)
    
    for c in contexts:
        if not c.maps_url:
            continue
            
        title = normalize_text(c.title or "")
        # Clean title: take first part and remove "taranto" suffix if present
        clean_title = title.split(" taranto")[0].strip()
        significant_words = [w for w in clean_title.split() if len(w) > 3]
        
        is_mentioned = False
        if clean_title and clean_title in norm_ans:
            is_mentioned = True
        elif significant_words and all(w in norm_ans for w in significant_words):
            is_mentioned = True
        elif c.address and normalize_text(c.address) in norm_ans:
            is_mentioned = True
            
        if is_mentioned:
            if c.maps_url not in mentioned_maps:
                mentioned_maps.append(c.maps_url)
    
    maps = None
    if len(mentioned_maps) == 1:
        # Exactly one location mentioned
        maps = mentioned_maps[0]
        # Show icon ONLY on the first source that matches this location
        icon_shown = False
        for s in sources:
            if s.maps_url == maps and not icon_shown:
                icon_shown = True
            else:
                s.maps_url = None
        
        # Ensure the source with the map is first if it's the only one
        if icon_shown:
            map_source = next((s for s in sources if s.maps_url == maps), None)
            if map_source:
                sources.remove(map_source)
                sources.insert(0, map_source)

    elif len(mentioned_maps) > 1:
        # Multiple locations mentioned: hide all icons and add suffix
        for s in sources:
            s.maps_url = None
        maps = None
        suffix = " Vuoi sapere la posizione di un posto specifico tra questi?"
        if suffix not in answer:
            answer = f"{answer.rstrip()} {suffix}".strip()
    else:
        maps = first_relevant_map(contexts, plan)
        icon_shown = False
        for s in sources:
            if maps and s.maps_url == maps and not icon_shown:
                icon_shown = True
            else:
                s.maps_url = None

    latency_ms = (time.perf_counter() - started_at) * 1000
    
    response = ChatResponseDTO(
        session_id=session_id,
        conversation_id=conversation_id,
        user_message_id=user_message_row["id"],
        answer=answer,
        language=plan.response_language, # POPULATE THE LANGUAGE FIELD
        sources=sources,
        maps=maps,
        should_escalate=should_escalate,
        needs_email_for_ticket=should_escalate,
        reason=reason,
        ticket_draft=build_ticket_draft(message, plan, reason, contexts)
        if should_escalate
        else None,
    )

    bot_message_row = save_bot_message(session_id, answer)
    response.bot_message_id = bot_message_row["id"]
    response.message_id = bot_message_row["id"]

    logger.info(
        "chat query=%r language=%s intent=%s domains=%s filters=%s retrieved_ids=%s answer_context_ids=%s sources=%s "
        "should_escalate=%s reason=%s latency_ms=%.2f",
        message,
        plan.response_language,
        plan.intent,
        plan.domains,
        plan.filters,
        [candidate.item_id for candidate in candidates],
        [candidate.item_id for candidate in answer_candidates],
        [s.url for s in sources],
        should_escalate,
        reason,
        latency_ms,
    )

    return response


def normalize_required_message(value: str) -> str:
    message = value.strip()
    if not message:
        from backend.app.services.errors import ValidationServiceError

        raise ValidationServiceError("Message cannot be empty.")
    return message


def ai_disabled_answer(language: str | None) -> str:
    match (language or "it").lower():
        case "en":
            return "AI models are disabled in this local demo mode. I saved your message, but I cannot generate a grounded answer right now."
        case "es":
            return "Los modelos de IA están desactivados en este modo local de demostración. He guardado tu mensaje, pero ahora no puedo generar una respuesta fundamentada."
        case "fr":
            return "Les modèles d'IA sont désactivés dans ce mode local de démonstration. J'ai enregistré votre message, mais je ne peux pas générer une réponse fiable pour le moment."
        case "ar":
            return "نماذج الذكاء الاصطناعي معطلة في وضع العرض المحلي. تم حفظ رسالتك، لكن لا يمكنني إنشاء إجابة موثوقة الآن."
        case _:
            return "I modelli AI sono disattivati in questa modalità demo locale. Ho salvato il tuo messaggio, ma al momento non posso generare una risposta grounded."


def build_sources(
    contexts: list[RetrievedContext],
    plan: QueryPlan,
) -> list[SourceDTO]:
    sources: list[SourceDTO] = []
    seen_urls: set[str] = set()

    for context in contexts:
        if not context.source_url:
            continue
            
        url = canonical_source_url(context.source_url)
        if url in seen_urls:
            continue
            
        sources.append(
            SourceDTO(
                title=context.title,
                url=context.source_url,
                type=context.item_type,
                maps_url=context.maps_url,
            )
        )
        seen_urls.add(url)
        if len(sources) == 4: # Allow up to 4 sources if unique
            break
    return sources


def canonical_source_url(url: str) -> str:
    parsed = urlparse(url.strip().lower())
    if parsed.netloc:
        return parsed.netloc.removeprefix("www.")
    return url.strip().lower().rstrip("/")


def select_source_contexts(
    contexts: list[RetrievedContext],
    plan: QueryPlan,
) -> list[RetrievedContext]:
    return contexts


def build_map_link(
    contexts: list[RetrievedContext],
    plan: QueryPlan,
) -> str | None:
    if not should_return_map(plan, contexts):
        return None

    filters = meaningful_terms(plan) or set(plan.filters)
    matching_urls: list[str] = []

    for context in contexts:
        if not context.maps_url:
            continue
        if filters and not context_matches_filters(context, filters):
            continue
        if context.maps_url not in matching_urls:
            matching_urls.append(context.maps_url)

    if len(matching_urls) == 1:
        return matching_urls[0]
    return None


def should_return_map(
    plan: QueryPlan,
    contexts: list[RetrievedContext],
) -> bool:
    if not contexts or plan.domain in {"history", "ticketing", "contacts"}:
        return False
    if not any(context.maps_url for context in contexts):
        return False

    normalized = normalize_text(plan.original_query)
    asks_map_or_location = contains_any(normalized, MAP_REQUEST_TERMS)
    if plan.domain == "venue":
        return True
    if plan.domain in {"calendar", "city_sports", "accessibility"}:
        return asks_map_or_location
    return False


def is_mobility_request(message: str) -> bool:
    return contains_any(normalize_text(message), MOBILITY_REQUEST_TERMS)


def build_mobility_answer(
    plan: QueryPlan,
    contexts: list[RetrievedContext],
) -> str | None:
    venue_context = first_venue_context(contexts)
    if not venue_context:
        return None

    venue_name = venue_context.title or "la sede indicata"
    if not is_taranto_context(venue_context):
        return (
            f"{venue_name} risulta fuori Taranto: con i dati disponibili Kyma non "
            "ha corse urbane verso questa sede. Posso indicarti indirizzo e posizione, "
            "ma non linee Kyma per raggiungerla."
        )

    public_transport = extract_labeled_value(
        venue_context.document,
        "Per i trasporti pubblici",
    )
    parking = extract_labeled_value(venue_context.document, "Per il parcheggio")
    timetable = extract_labeled_value(venue_context.document, "Orari")
    bus_lines = extract_bus_lines(public_transport or "")
    if not public_transport:
        return (
            f"Per {venue_name} ho indirizzo e posizione, ma nei dati Kyma disponibili "
            "non sono indicate linee o fermate bus specifiche."
        )

    origin = extract_origin(plan.original_query)
    lines_text = f"queste linee bus: {', '.join(bus_lines)}" if bus_lines else public_transport
    address_text = f" La sede si trova in {venue_context.address}." if venue_context.address else ""
    origin_text = (
        f" Partendo da {origin}, usa queste linee come riferimento per raggiungere la zona della sede."
        if origin
        else ""
    )
    parking_text = f" Parcheggio disponibile: {parking}." if parking else ""
    timetable_text = (
        f" Orari indicati nei dati Kyma: {timetable}."
        if timetable
        else " Orari: nella KB locale non sono presenti orari di passaggio o cambi intermedi per questa tratta."
    )
    return (
        f"Per arrivare a {venue_name}, dai dati Kyma risultano {lines_text}. "
        f"La fermata di riferimento e' quella della sede: {public_transport}.{address_text}"
        f"{origin_text}{timetable_text}{parking_text}"
    )


def ensure_mobility_context(
    message: str,
    contexts: list[RetrievedContext],
) -> list[RetrievedContext]:
    kb_context = find_venue_context_in_kb(message)
    if kb_context:
        remaining_contexts = [
            context
            for context in contexts
            if context.item_id != kb_context.item_id
        ]
        return [kb_context, *remaining_contexts]
    if first_venue_context(contexts):
        return contexts
    return contexts


def find_venue_context_in_kb(message: str) -> RetrievedContext | None:
    normalized_message = normalize_text(message)
    normalized_message = normalize_venue_aliases(normalized_message)
    best_record: dict[str, Any] | None = None
    best_score = 0

    for record in mobility_records():
        metadata = record.get("metadata") or {}
        title = str(metadata.get("title") or "")
        document = str(record.get("document") or "")
        text = normalize_venue_aliases(normalize_text(f"{record.get('id')} {title} {document}"))
        title_tokens = [token for token in normalize_text(title).split() if len(token) > 3]
        id_tokens = [
            token
            for token in normalize_text(record.get("id") or "").split()
            if len(token) > 3
        ]
        score = sum(8 for token in title_tokens if token in normalized_message)
        score += sum(3 for token in id_tokens if token in normalized_message)
        score += sum(1 for token in normalized_message.split() if len(token) > 3 and token in text)
        if score > best_score:
            best_score = score
            best_record = record

    if not best_record or best_score < 8:
        return None
    return record_to_context(best_record)


def normalize_venue_aliases(value: str) -> str:
    replacements = {
        "iacovone": "erasmo iacovone stadio",
        "pala mazzola": "palamazzola",
        "pala ricciardi": "palaricciardi",
        "pala wojtyla": "palawojtyla",
    }
    normalized = value
    for source, target in replacements.items():
        normalized = normalized.replace(source, f"{source} {target}")
    return normalized


@lru_cache(maxsize=1)
def mobility_records() -> tuple[dict[str, Any], ...]:
    try:
        records = load_jsonl(settings.kb_path)
    except Exception as exc:
        logger.warning("mobility_kb_lookup_unavailable error=%s", exc)
        return ()
    return tuple(
        record
        for record in records
        if (record.get("metadata") or {}).get("type") == "venue_geocoding"
    )


def record_to_context(record: dict[str, Any]) -> RetrievedContext:
    metadata = record.get("metadata") or {}
    latitude = optional_float(metadata.get("latitude"))
    longitude = optional_float(metadata.get("longitude"))
    maps_url = google_maps_url(latitude, longitude) if latitude is not None and longitude is not None else None
    return RetrievedContext(
        item_id=str(record.get("id") or ""),
        title=optional_text(metadata.get("title")),
        item_type=optional_text(metadata.get("type")),
        source_url=optional_text(metadata.get("source_url")),
        address=optional_text(metadata.get("address")),
        latitude=latitude,
        longitude=longitude,
        maps_url=maps_url,
        document=str(record.get("document") or ""),
    )


def optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def first_venue_context(contexts: list[RetrievedContext]) -> RetrievedContext | None:
    for context in contexts:
        if context_type(context) == "venue_geocoding":
            return context
    for context in contexts:
        if context_type(context) == "venue":
            return context
    return None


def is_taranto_context(context: RetrievedContext) -> bool:
    text = normalize_text(" ".join(part for part in (context.address, context.document) if part))
    return "taranto" in text or "741" in text


def extract_labeled_value(document: str, label: str) -> str | None:
    match = re.search(rf"{re.escape(label)}:\s*([^\.]+)", document, flags=re.IGNORECASE)
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(1)).strip()


def extract_bus_lines(public_transport: str) -> list[str]:
    match = re.search(r"linee?\s+([0-9,\s]+)", public_transport, flags=re.IGNORECASE)
    if not match:
        return []
    return [line.strip() for line in match.group(1).split(",") if line.strip()]


def extract_origin(message: str) -> str | None:
    patterns = (
        r"\b(?:sono|sto|abito|parto)\s+(?:a|ai|agli|alle|in|da|dai|dagli|dalle)\s+([^,?.]+)",
        r"\bda\s+([^,?.]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            origin = re.sub(r"\s+", " ", match.group(1)).strip()
            return origin[:80] if origin else None
    return None


def first_relevant_map(
    contexts: list[RetrievedContext],
    plan: QueryPlan,
) -> str | None:
    if not should_return_map(plan, contexts) and not is_mobility_request(plan.original_query):
        return None
    for context in contexts:
        if context.maps_url:
            return context.maps_url
    return None


def context_matches_filters(context: RetrievedContext, filters: set[str]) -> bool:
    text = normalize_text(
        " ".join(
            item
            for item in (
                context.title,
                context.item_type,
                context.address,
                context.document,
            )
            if item
        )
    )
    return any(term in text for term in filters)


def escalation_decision(
    plan: QueryPlan,
    contexts: list[RetrievedContext],
    candidates: list[RetrievalCandidate],
) -> tuple[bool, str | None]:
    normalized = normalize_text(plan.original_query)
    if contains_any(normalized, URGENT_TERMS):
        return True, "urgent_request"
    if contains_any(normalized, HUMAN_OPERATOR_TERMS):
        return True, "human_operator_requested"
    if contains_any(normalized, LIVE_DATA_TERMS):
        return True, "live_data_unavailable"
    if contains_any(normalized, COMPLAINT_TERMS):
        return True, "complaint_or_lost_item"
    if contains_any(normalized, OFFICIAL_VERIFICATION_TERMS):
        return True, "official_verification_requested"
    if not contexts:
        if candidates:
            return True, "insufficient_context"
        return True, "no_context"
    return False, None


def build_ticket_draft(
    message: str,
    plan: QueryPlan,
    reason: str | None,
    contexts: list[RetrievedContext],
) -> TicketDraftDTO:
    context_summary = "; ".join(
        context.title or context.item_type or "Fonte recuperata"
        for context in contexts[:3]
    )
    if not context_summary:
        context_summary = "Nessun contesto affidabile recuperato."

    return TicketDraftDTO(
        category=ticket_category(plan.domain, reason),
        summary=summarize_for_ticket(message),
        user_message=message,
        retrieved_context_summary=(
            f"Intent rilevato: {plan.intent}. Domini: {', '.join(plan.domains)}. Motivo escalation: "
            f"{reason or 'non specificato'}. Contesto: {context_summary}"
        ),
        priority=priority_for_message(reason, plan.domains, message),
    )


def ticket_category(domain: str, reason: str | None = None) -> str:
    if reason == "complaint_or_lost_item":
        return "complaint"
    mapping = {
        "ticketing": "ticketing",
        "venue": "venue_information",
        "calendar": "calendar",
        "volunteering": "volunteering",
        "contacts": "general_information",
        "accessibility": "accessibility",
        "partnership": "partnership",
        "school_project": "school_project",
    }
    return mapping.get(domain, "general_information")


def ticket_priority(reason: str | None, domains: list[str] | None = None) -> str:
    if reason == "urgent_request":
        return "high"
    normalized_domains = {context_type_name(domain) for domain in (domains or [])}
    if normalized_domains & {"accessibility", "security", "safety"}:
        return "high"
    if normalized_domains & {
        "contacts",
        "partnership",
        "school_project",
        "ticketing",
        "venue",
        "volunteering",
    }:
        return "medium"
    if reason in {
        "human_operator_requested",
        "live_data_unavailable",
        "official_verification_requested",
        "complaint_or_lost_item",
    }:
        return "medium"
    return "medium"


def priority_for_message(reason: str | None, domains: list[str] | None, message: str) -> str:
    normalized = normalize_text(message)
    if looks_useless_request(normalized):
        return "low"
    if not is_event_related(normalized):
        if reason == "urgent_request":
            return "high"
        if reason in {
            "human_operator_requested",
            "live_data_unavailable",
            "official_verification_requested",
            "complaint_or_lost_item",
        } or contains_any(normalized, HUMAN_OPERATOR_TERMS + OFFICIAL_VERIFICATION_TERMS + COMPLAINT_TERMS):
            return "medium"
        return "low"
    return ticket_priority(reason, domains)


def looks_useless_request(normalized_message: str) -> bool:
    if len(normalized_message) <= 3:
        return True
    if normalized_message in USELESS_REQUEST_TERMS:
        return True
    return False


def is_event_related(normalized_message: str) -> bool:
    return contains_any(normalized_message, EVENT_RELATED_TERMS)


def context_type_name(value: str | None) -> str:
    return normalize_text(value or "").replace(" ", "_")


def summarize_for_ticket(message: str) -> str:
    compacted = re.sub(r"\s+", " ", message).strip()
    if len(compacted) <= 90:
        return compacted
    return compacted[:87].rstrip() + "..."


def meaningful_terms(plan: QueryPlan) -> set[str]:
    terms = set(plan.filters)
    terms.update(value for value in plan.entities.values() if value)
    return {normalize_text(term) for term in terms if len(normalize_text(term)) > 2}


def context_type(context: RetrievedContext) -> str:
    return normalize_text(context.item_type).replace(" ", "_")
