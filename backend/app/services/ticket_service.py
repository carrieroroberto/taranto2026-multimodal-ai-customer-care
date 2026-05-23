import logging
import re
from typing import Any

from backend.app.repositories.persistence_repository import get_conversation_messages
from backend.app.services.llm_service import translate_text


logger = logging.getLogger(__name__)


def generate_ticket_triage(conversation_id: str) -> dict[str, Any]:
    messages = get_conversation_messages(conversation_id)
    if not messages:
        return {
            "domain": "general",
            "priority": "medium",
            "summary": "Ticket creato senza messaggi.",
            "original_message": "Nessun messaggio trovato.",
            "translated_message": None,
        }

    # Find the last user message
    user_messages = [m for m in messages if m["role"] == "user"]
    last_user_message = user_messages[-1] if user_messages else messages[-1]
    
    content = last_user_message["content"]
    
    # 1. TRANSLATION LOGIC
    translated_message = None
    try:
        logger.info("DEBUG: Starting triage translation for content: %r", content[:100])
        translated = translate_text(content, "it")
        logger.info("DEBUG: LLM returned translation: %r", (translated or "NONE")[:100])
        
        if translated and translated.strip().lower() != content.strip().lower():
            translated_message = translated
            logger.info("DEBUG: SETTING translated_message = %r", translated_message[:50])
        else:
            logger.info("DEBUG: SKIPPING translation (identical or empty)")
    except Exception as e:
        logger.error("DEBUG: Ticket translation CRITICAL ERROR: %s", e)

    # ... triage logic continues

    # Fallback logic as requested
    domain = "general"
    priority = "medium"
    
    # Try to detect some domains based on keywords (simple version)
    content_lower = content.lower()
    if any(k in content_lower for k in ["bigliett", "ticket", "costo", "prezzo", "pagamento"]):
        domain = "ticketing"
    elif any(k in content_lower for k in ["trasport", "autobus", "navetta", "treno", "parcheggio"]):
        domain = "transport"
    elif any(k in content_lower for k in ["calendario", "orario", "quando", "data"]):
        domain = "schedule"
    elif any(k in content_lower for k in ["accessibil", "disabil", "carrozzina"]):
        domain = "accessibility"
    elif any(k in content_lower for k in ["reclamo", "lament", "problema", "non funzion"]):
        domain = "complaint"

    # Priority logic
    if any(k in content_lower for k in ["urgent", "emergenza", "pericol", "aiuto"]):
        priority = "high"

    summary = summarize_text(content)
    
    return {
        "domain": domain,
        "priority": priority,
        "summary": summary,
        "original_message": content,
        "translated_message": translated_message,
    }


def summarize_text(text: str, max_len: int = 100) -> str:
    compacted = re.sub(r"\s+", " ", text).strip()
    if len(compacted) <= max_len:
        return compacted
    return compacted[:max_len-3].rstrip() + "..."
