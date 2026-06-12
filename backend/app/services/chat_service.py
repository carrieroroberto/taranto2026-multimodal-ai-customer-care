import logging
import time
from typing import Any

from backend.app.config import settings
from backend.app.repositories.persistence_repository import (
    ensure_conversation,
    get_session_history,
    save_bot_message,
    save_user_message,
)
from backend.app.services.llm_service import (
    normalize_language_code,
    normalize_text,
)
from backend.app.schemas.chat import ChatRequestDTO, ChatResponseDTO, SourceDTO, TicketDraftDTO
from backend.app.services.agent_orchestrator import run_agent_orchestration
from backend.app.services.llm_service import normalize_required_message

logger = logging.getLogger(__name__)

def ai_disabled_answer(language: str | None) -> str:
    match (language or "it").lower():
        case "en":
            return "AI models are disabled in this mode. I saved your message, but I cannot generate a precise answer right now."
        case "es":
            return "Los modelos de IA están desactivados en esta modalidad. He guardado tu mensaje, pero ahora no puedo generar una respuesta precisa."
        case "fr":
            return "Les modèles d'IA sont désactivés dans ce mode. J'ai enregistré votre message, mais je ne peux pas générer une réponse précise pour le moment."
        case "ar":
            return "نماذج الذكاء الاصطناعي معطلة في هذه الوضعية. تم حفظ رسالتك، لكن لا يمكنني إنشاء إجابة دقيقة الآن."
        case _:
            return "I modelli AI sono disattivati in questa modalità. Ho salvato il tuo messaggio, ma al momento non posso generare una risposta precisa."


def groq_is_configured() -> bool:
    api_key = (settings.groq_api_key or "").strip().strip('"').strip("'")
    return bool(api_key and "your_groq" not in api_key.lower())


async def answer_chat(request: ChatRequestDTO) -> ChatResponseDTO:
    started_at = time.perf_counter()
    message = normalize_required_message(request.message)
    session_id = request.session_id
    conversation_id = ensure_conversation(session_id=session_id)

    # Load history
    history = get_session_history(session_id)
    user_message_row = save_user_message(
        session_id,
        request.stored_user_content or message,
        request.message_type,
        request.media_url,
        caption=request.caption or (request.stored_user_content if request.message_type == "image" else None),
    )
    ui_lang = normalize_language_code(request.language) if request.language else "it"

    if settings.ai_disabled and not groq_is_configured():
        answer = ai_disabled_answer(ui_lang)
        bot_message_row = save_bot_message(session_id, answer, [])
        return ChatResponseDTO(
            session_id=session_id,
            conversation_id=conversation_id,
            user_message_id=user_message_row["id"],
            bot_message_id=bot_message_row["id"],
            message_id=bot_message_row["id"],
            user_created_at=str(user_message_row.get("created_at")) if user_message_row.get("created_at") else None,
            bot_created_at=str(bot_message_row.get("created_at")) if bot_message_row.get("created_at") else None,
            answer=answer,
            language=ui_lang,
            sources=[],
            maps=None,
            should_escalate=False,
            reason="ai_disabled",
            ticket_draft=None,
        )
    
    # Run LangGraph Orchestration
    result = await run_agent_orchestration(
        message=message,
        history=history,
        language=ui_lang,
        visual_context=request.visual_context
    )
    
    # IMPORTANT: Use the processed results from the orchestrator directly!
    answer = result["answer"]
    should_escalate = result["should_escalate"]
    reason = result["escalation_reason"]
    plan = result["plan"]
    contexts = result["contexts"]
    sources = result["sources"] # These are already prioritized and have maps_url
    maps = result["maps"]

    latency_ms = (time.perf_counter() - started_at) * 1000
    
    bot_message_row = save_bot_message(session_id, answer, sources)
    
    response = ChatResponseDTO(
        session_id=session_id,
        conversation_id=conversation_id,
        user_message_id=user_message_row["id"],
        bot_message_id=bot_message_row["id"],
        message_id=bot_message_row["id"],
        user_created_at=str(user_message_row.get("created_at")) if user_message_row.get("created_at") else None,
        bot_created_at=str(bot_message_row.get("created_at")) if bot_message_row.get("created_at") else None,
        answer=answer,
        language=plan.response_language if plan else ui_lang,
        language_detected=bool(plan.language_detected) if plan else False,
        sources=sources,
        maps=maps,
        should_escalate=should_escalate,
        needs_email_for_ticket=should_escalate,
        reason=reason,
        ticket_draft=build_ticket_draft(message, plan, reason, contexts) if should_escalate else None
    )

    logger.info(
        "chat_langgraph query=%r language=%s should_escalate=%s reason=%s latency_ms=%.2f",
        message,
        response.language,
        should_escalate,
        reason,
        latency_ms,
    )

    return response

def build_ticket_draft(
    message: str,
    plan: Any,
    reason: str | None,
    contexts: list[Any],
) -> TicketDraftDTO:
    from backend.app.schemas.chat import TicketDraftDTO
    
    context_summary = "; ".join(
        getattr(ctx, 'title', None) or getattr(ctx, 'item_id', 'Fonte')
        for ctx in contexts[:3]
    )
    
    return TicketDraftDTO(
        category="general_information",
        summary=message[:90],
        user_message=message,
        retrieved_context_summary=f"Reason: {reason}. Context: {context_summary}",
        priority="media"
    )
