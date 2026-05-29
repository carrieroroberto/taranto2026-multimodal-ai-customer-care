import logging
import re
import unicodedata
from typing import Any

from backend.app.repositories.persistence_repository import (
    get_conversation_messages,
    get_kb_source_domains,
    get_kb_sources_for_triage,
)
from backend.app.services.llm_service import translate_text, generate_conversation_summary


logger = logging.getLogger(__name__)


def generate_ticket_triage(conversation_id: str) -> dict[str, Any]:
    messages = get_conversation_messages(conversation_id)
    if not messages:
        return {
            "domain": "general",
            "priority": "medium",
            "summary": "Ticket creato senza messaggi.",
            "ai_summary": "Nessuna conversazione disponibile.",
            "original_message": "Nessun messaggio trovato.",
            "translated_message": None,
        }

    # Find the last user message for other triage fields
    user_messages = [m for m in messages if m["role"] == "user"]
    last_user_message = user_messages[-1] if user_messages else messages[-1]
    
    content = last_user_message["content"]
    fallback_summary = build_fallback_conversation_summary(messages)

    # Generate a concise Italian AI summary of the whole conversation for the operator dashboard.
    ai_summary = generate_conversation_summary(messages)
    if not is_usable_ai_summary(ai_summary):
        ai_summary = fallback_summary
    
    # 1. TRANSLATION LOGIC
    translated_message = None
    try:
        translated = translate_text(content, "it")
        if translated and translated.strip().lower() != content.strip().lower():
            translated_message = translated
    except Exception as e:
        logger.error("Ticket translation error: %s", e)

    domain = detect_ticket_domain(content, "")
    priority = priority_for_ticket(content, domain)
    
    return {
        "domain": domain,
        "priority": priority,
        "summary": summarize_text(ai_summary, 160),
        "ai_summary": ai_summary,
        "original_message": content,
        "translated_message": translated_message,
    }


HIGH_PRIORITY_TERMS = (
    "urgente",
    "urgent",
    "emergenza",
    "emergency",
    "pericolo",
    "danger",
    "sicurezza",
    "security",
    "safety",
    "soccorso",
    "aiuto immediato",
)

MEDIUM_PRIORITY_TERMS = (
    "reclamo",
    "lamentela",
    "problema",
    "non funziona",
    "errore",
    "bloccato",
    "oggetto smarrito",
    "lost item",
    "operatore",
    "assistenza",
    "support",
)

DOMAIN_PRIORITY = {
    "accessibility": "high",
    "contacts": "medium",
    "faq": "medium",
    "partnership": "medium",
    "school_project": "medium",
    "tender_notice": "medium",
    "ticketing": "medium",
    "venue": "medium",
    "volunteers": "medium",
}
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
    "iacovone",
)

DOMAIN_ALIASES = {
    "ticketing": ("bigliett", "ticket", "costo", "prezzo", "pagamento", "acquisto"),
    "venue": ("sede", "impianto", "stadio", "palazzetto", "dove", "indirizzo"),
    "event_schedule": ("calendario", "orario", "quando", "data", "programma", "gara"),
    "accessibility": ("accessibil", "disabil", "carrozzina", "barriere"),
    "volunteers": ("volontar", "volunteer"),
    "partnership": ("partner", "sponsor", "partnership"),
    "school_project": ("scuola", "student", "progetto scuola"),
    "contacts": ("contatto", "email", "telefono", "segreteria"),
    "tender_notice": ("bando", "avviso", "gara d'appalto", "appalto"),
}


def detect_ticket_domain(content: str, summary: str) -> str:
    text = normalize_for_triage(f"{content} {summary}")
    tokens = set(text.split())
    best_domain = "general_information"
    best_score = 0

    try:
        sources = get_kb_sources_for_triage()
    except Exception as exc:
        logger.warning("kb domain triage unavailable: %s", exc)
        sources = []

    for source in sources:
        source_text = normalize_for_triage(
            " ".join(
                str(source.get(field) or "")
                for field in ("id", "domain_label", "title", "source_url", "search_text")
            )
        )
        score = score_domain_match(text, tokens, source_text)
        if score > best_score:
            best_score = score
            best_domain = str(source.get("domain_label") or best_domain)

    for domain, aliases in DOMAIN_ALIASES.items():
        alias_score = sum(4 for alias in aliases if alias in text)
        if alias_score > best_score:
            best_score = alias_score
            best_domain = domain

    return best_domain


def score_domain_match(query_text: str, query_tokens: set[str], source_text: str) -> int:
    score = 0
    for token in query_tokens:
        if len(token) < 4:
            continue
        if token in source_text:
            score += 1
    if query_text and query_text in source_text:
        score += 8
    return score


def priority_for_ticket(content: str, domain: str) -> str:
    text = normalize_for_triage(content)
    if looks_useless_request(text):
        return "low"
    if contains_any(text, HIGH_PRIORITY_TERMS):
        return "high"
    if contains_any(text, MEDIUM_PRIORITY_TERMS):
        return "medium"
    if not is_event_related(text):
        return "low"
    return DOMAIN_PRIORITY.get(domain, "medium")


def looks_useless_request(normalized_text: str) -> bool:
    if len(normalized_text) <= 3:
        return True
    return normalized_text in USELESS_REQUEST_TERMS


def is_event_related(normalized_text: str) -> bool:
    return contains_any(normalized_text, EVENT_RELATED_TERMS)


def normalize_for_triage(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9']+", " ", text.lower()).strip()


def contains_any(haystack: str, terms: tuple[str, ...]) -> bool:
    return any(term in haystack for term in terms)


def summarize_text(text: str, max_len: int = 100) -> str:
    compacted = re.sub(r"\s+", " ", text).strip()
    if len(compacted) <= max_len:
        return compacted
    return compacted[:max_len-3].rstrip() + "..."


def is_usable_ai_summary(summary: str | None) -> bool:
    if not summary or not summary.strip():
        return False
    normalized = summary.strip().lower()
    return not (
        normalized.startswith("errore durante")
        or normalized.startswith("impossibile generare")
    )


def build_fallback_conversation_summary(messages: list[dict[str, Any]]) -> str:
    user_messages = [
        summarize_text(str(message.get("content") or ""), 180)
        for message in messages
        if message.get("role") == "user" and str(message.get("content") or "").strip()
    ]
    if not user_messages:
        return "L'utente ha richiesto assistenza, ma non sono presenti messaggi utente leggibili nella conversazione."

    first_message = user_messages[0]
    last_message = user_messages[-1]
    if len(user_messages) == 1 or first_message == last_message:
        return f"L'utente ha richiesto assistenza su: {last_message}"

    return (
        f"L'utente ha richiesto assistenza. Primo messaggio: {first_message}. "
        f"Ultimo messaggio: {last_message}."
    )
