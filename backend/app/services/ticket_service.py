import logging
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.app.repositories.persistence_repository import (
    get_conversation_messages,
)
from backend.app.config import settings
from backend.app.services.llm_service import generate_conversation_summary


logger = logging.getLogger(__name__)


async def generate_ticket_triage(conversation_id: str) -> dict[str, Any]:
    messages = get_conversation_messages(conversation_id)
    if not messages:
        return {
            "domain": "informazioni generali",
            "priority": "media",
            "summary": "Ticket creato senza messaggi.",
        }

    escalation_message = find_escalation_message(messages)
    content = escalation_message["content"]
    fallback_summary = build_fallback_conversation_summary(messages)

    # Generate a concise Italian summary focused on the message that opened escalation.
    generated_summary = await generate_conversation_summary(messages, escalation_message)
    if not is_usable_summary(generated_summary):
        generated_summary = fallback_summary
    
    raw_domain = detect_ticket_domain(content, generated_summary)
    priority = priority_for_ticket(content, raw_domain)
    
    return {
        "domain": localize_ticket_domain(raw_domain),
        "priority": priority,
        "summary": generated_summary,
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
    "accessibility": "alta",
    "contacts": "media",
    "faq": "media",
    "partnership": "media",
    "school_project": "media",
    "tender_notice": "media",
    "ticketing": "media",
    "venue": "media",
    "volunteers": "media",
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

    for record in load_triage_knowledge_records():
        score = score_knowledge_match(text, tokens, record["search_text"])
        if score > best_score:
            best_score = score
            best_domain = record["domain"]

    for domain, aliases in DOMAIN_ALIASES.items():
        alias_score = sum(4 for alias in aliases if alias in text)
        if alias_score > best_score:
            best_score = alias_score
            best_domain = domain

    return best_domain


def localize_ticket_domain(domain: str | None) -> str:
    normalized = str(domain or "").strip().lower()
    return {
        "general": "informazioni generali",
        "general_information": "informazioni generali",
        "games general": "informazioni generali",
        "games_general": "informazioni generali",
        "unknown": "informazioni generali",
        "ticketing": "biglietteria",
        "venue": "impianti",
        "venue_information": "impianti",
        "event_schedule": "calendario",
        "calendar": "calendario",
        "schedule": "calendario",
        "transport": "trasporti",
        "accessibility": "accessibilita",
        "volunteering": "volontariato",
        "volunteers": "volontariato",
        "contacts": "contatti",
        "complaint": "reclamo",
        "partnership": "partnership",
        "school_project": "progetto scuola",
        "tender_notice": "bandi e avvisi",
        "organizing committee": "comitato organizzatore",
        "organizing_committee": "comitato organizzatore",
        "historical results page": "risultati storici",
        "historical_results_page": "risultati storici",
        "sport": "sport",
        "faq": "faq",
    }.get(normalized, "informazioni generali")


@lru_cache(maxsize=1)
def load_triage_knowledge_records() -> tuple[dict[str, str], ...]:
    path = Path(settings.kb_path)
    if not path.exists():
        logger.warning("ticket triage knowledge file not found: %s", path)
        return ()

    records: list[dict[str, str]] = []
    try:
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                record = json.loads(line)
                metadata = record.get("metadata") or {}
                domain = str(metadata.get("type") or "general_information").strip()
                if not domain:
                    domain = "general_information"
                search_text = normalize_for_triage(
                    " ".join(
                        str(part or "")
                        for part in (
                            record.get("id"),
                            domain,
                            metadata.get("title"),
                            metadata.get("source_url"),
                            record.get("document"),
                        )
                    )
                )
                if search_text:
                    records.append({"domain": domain, "search_text": search_text})
    except Exception as exc:
        logger.warning("ticket triage knowledge load failed: %s", exc)
        return ()

    return tuple(records)


def score_knowledge_match(query_text: str, query_tokens: set[str], source_text: str) -> int:
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
        return "bassa"
    if contains_any(text, HIGH_PRIORITY_TERMS):
        return "alta"
    if contains_any(text, MEDIUM_PRIORITY_TERMS):
        return "media"
    if not is_event_related(text):
        return "bassa"
    return DOMAIN_PRIORITY.get(domain, "media")


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


def is_usable_summary(summary: str | None) -> bool:
    if not summary or not summary.strip():
        return False
    normalized = summary.strip().lower()
    return not (
        normalized.startswith("errore durante")
        or normalized.startswith("impossibile generare")
    )


def build_fallback_conversation_summary(messages: list[dict[str, Any]]) -> str:
    escalation_message = find_escalation_message(messages)
    user_messages = [clean_message_content(str(message.get("content") or "")) for message in messages if message.get("role") == "user"]
    user_messages = [summarize_text(message, 180) for message in user_messages if message.strip()]
    if not user_messages:
        return "L'utente ha richiesto assistenza, ma non sono presenti messaggi utente leggibili nella conversazione."

    escalation_text = summarize_text(clean_message_content(str(escalation_message.get("content") or "")), 220)
    if len(user_messages) == 1:
        return f"L'utente ha richiesto assistenza su: {escalation_text}"

    return (
        f"L'utente ha richiesto assistenza su: {escalation_text}. "
        f"Contesto precedente: {summarize_text(user_messages[0], 120)}"
    )


def find_escalation_message(messages: list[dict[str, Any]]) -> dict[str, Any]:
    if not messages:
        return {"role": "user", "content": ""}

    negative_bot_indexes = [
        index
        for index, message in enumerate(messages)
        if message.get("role") == "bot" and message.get("satisfaction") is False
    ]

    if negative_bot_indexes:
        bot_index = negative_bot_indexes[-1]
        for index in range(bot_index - 1, -1, -1):
            if messages[index].get("role") == "user" and str(messages[index].get("content") or "").strip():
                return messages[index]

    for message in reversed(messages):
        if message.get("role") == "user" and str(message.get("content") or "").strip():
            return message

    return messages[-1]


def clean_message_content(content: str) -> str:
    text = re.sub(r"\[(?:IMAGE|AUDIO)_URL:[^\]]+\]", "", content or "")
    text = re.sub(r"Descrizione immagine:.*", "", text, flags=re.DOTALL)
    text = re.sub(r"Testo estratto dall'immagine:.*", "", text, flags=re.DOTALL)
    return re.sub(r"\s+", " ", text).strip()
