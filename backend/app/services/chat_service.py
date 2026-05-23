import logging
import re
import time
import uuid
from typing import Any

from backend.app.config import settings
from backend.app.schemas import ChatRequestDTO, ChatResponseDTO, SourceDTO, TicketDraftDTO
from backend.app.repositories.persistence_repository import (
    ensure_conversation,
    get_session_history,
    save_bot_message,
    save_user_message,
)
from backend.app.services.llm_service import build_answer, build_query_plan, contains_any, normalize_text
from backend.app.services.rag_service import (
    QueryPlan,
    RetrievalCandidate,
    RetrievedContext,
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
    plan = build_query_plan(planning_message, history)
    
    if request.language:
        import dataclasses
        from backend.app.services.llm_service import normalize_language_code
        plan = dataclasses.replace(plan, response_language=normalize_language_code(request.language))
    
    if request.visual_context:
        import dataclasses
        from backend.app.services.rag_service import PlannedRetrievalQuery
        
        anchored_context = f"{request.visual_context} Giochi del Mediterraneo Taranto 2026 logo emblema mascotte icmg"
        
        new_queries = list(plan.retrieval_queries) + [
            PlannedRetrievalQuery(query=anchored_context, domain="general", weight=1.5),
            PlannedRetrievalQuery(query=request.visual_context, domain="general", weight=1.0)
        ]
        new_expanded = list(plan.expanded_queries) + [request.visual_context, anchored_context]
        plan = dataclasses.replace(plan, retrieval_queries=new_queries, expanded_queries=new_expanded)

    candidates = retrieve_context(plan, settings.n_results)
    answer_candidates = select_answer_candidates(candidates, plan)
    contexts = [to_context(candidate) for candidate in answer_candidates]
    
    should_escalate, reason = escalation_decision(plan, contexts, candidates)
    answer = build_answer(message, plan, contexts, should_escalate, reason, history)

    # The LLM can signal that the context was irrelevant by adding [NO_CONTEXT]
    llm_flagged_no_context = "[no_context]" in answer.upper() or "[NO_CONTEXT]" in answer
    if llm_flagged_no_context:
        answer = answer.replace("[NO_CONTEXT]", "").replace("[no_context]", "").strip()

    # Only provide sources if we actually have context AND the answer is not a refusal/fallback.
    normalized_answer = normalize_text(answer)
    refusal_keywords = [
        "informazioni sufficienti", 
        "dato abbastanza preciso", 
        "non ho informazioni", 
        "non risultano ancora disponibili",
        "non sono ancora pubblicati",
        "non dispongo di informazioni",
        "i don't have enough information",
        "non ho un dato",
        "domanda non e specifica",
        "indica cosa desideri sapere",
        "per favore specifica",
        "non posso rispondere",
        "non ho dettagli",
        "servizio e riservato a comunicazioni civili",
        "posso rispondere solo a domande riguardanti i giochi"
    ]
    is_refusal = llm_flagged_no_context or any(kw in normalized_answer for kw in refusal_keywords)
    
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
    elif len(mentioned_maps) > 1:
        # Multiple locations mentioned: hide all icons and add suffix
        for s in sources:
            s.maps_url = None
        maps = None
        suffix = " Vuoi sapere la posizione di un posto specifico tra questi?"
        if suffix not in answer:
            answer = f"{answer.rstrip()} {suffix}".strip()
    else:
        # No locations mentioned
        for s in sources:
            s.maps_url = None
        maps = None

    latency_ms = (time.perf_counter() - started_at) * 1000
    
    response = ChatResponseDTO(
        session_id=session_id,
        conversation_id=conversation_id,
        user_message_id=user_message_row["id"],
        answer=answer,
        sources=sources,
        maps=maps,
        should_escalate=should_escalate,
        reason=reason,
        ticket_draft=build_ticket_draft(message, plan, reason, contexts)
        if should_escalate
        else None,
    )

    bot_message_row = save_bot_message(session_id, answer)
    response.bot_message_id = bot_message_row["id"]

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


def build_sources(
    contexts: list[RetrievedContext],
    plan: QueryPlan,
) -> list[SourceDTO]:
    from urllib.parse import urlparse
    
    selected_contexts = sorted(
        select_source_contexts(contexts, plan),
        key=lambda context: 0
        if context.source_url and "ta2026.com" in context.source_url
        else 1,
    )
    sources: list[SourceDTO] = []
    seen_domains: set[str] = set()

    for context in selected_contexts:
        if not context.source_url:
            continue
            
        domain = urlparse(context.source_url).netloc.lower()
        if not domain or domain in seen_domains:
            continue
            
        sources.append(
            SourceDTO(
                title=context.title,
                url=context.source_url,
                type=context.item_type,
                maps_url=context.maps_url,
            )
        )
        seen_domains.add(domain)
        if len(sources) == 3:
            break
    return sources


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
        priority=ticket_priority(reason),
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


def ticket_priority(reason: str | None) -> str:
    if reason == "urgent_request":
        return "high"
    if reason in {
        "human_operator_requested",
        "live_data_unavailable",
        "official_verification_requested",
        "complaint_or_lost_item",
    }:
        return "medium"
    return "low"


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
