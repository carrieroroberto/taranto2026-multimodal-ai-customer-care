import logging
import re
import json
import unicodedata
import httpx
import asyncio
from typing import Any, Dict, List, Optional

from backend.app.config import settings
from backend.app.repositories.persistence_repository import save_bot_message
from backend.app.services.errors import DependencyServiceError, ValidationServiceError
from backend.app.services.rag_service import (
    QueryPlan,
    RetrievalCandidate,
    RetrievedContext,
    PlannedRetrievalQuery,
    retrieve_context,
    select_answer_candidates,
    to_context,
)
from backend.app.schemas.chat import ChatRequestDTO, ChatResponseDTO, SourceDTO, TicketDraftDTO
from backend.app.services.rag_service import parse_retrieval_queries, translate_static_answer
from groq import AsyncGroq

logger = logging.getLogger(__name__)

QUERY_PLAN_SYSTEM_PROMPT = """Sei un analista di query per i Giochi del Mediterraneo Taranto 2026.
Il tuo compito è analizzare la domanda dell'utente e produrre un piano di ricerca strutturato in JSON.
Identifica l'intento, i domini coinvolti, le entità e la lingua della risposta.
"""

VALID_INTENTS = {"general_information", "ticketing", "venue_information", "calendar", "volunteering", "accessibility"}
VALID_DOMAINS = {"general", "ticketing", "venue", "calendar", "volunteering", "accessibility"}
ENTITY_KEYS = {"sport", "venue", "atleta", "data"}
LANGUAGE_NAMES = {"it": "Italiano", "en": "Inglese", "es": "Spagnolo", "fr": "Francese", "ar": "Arabo"}

async def call_ollama(payload: dict[str, Any], timeout: float = 150.0) -> dict[str, Any]:
    url = f"{settings.ollama_base_url}/api/chat"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            if not data:
                logger.error("Ollama returned null JSON")
                return {}
            return data
    except Exception as exc:
        logger.error("Error calling Ollama (%s): %s", type(exc).__name__, str(exc) or "No error message")
        raise DependencyServiceError(f"Failed to reach Ollama: {exc}")

async def call_groq(messages: List[Dict[str, str]], timeout: float = 30.0) -> str:
    """Fallback call to Groq API using standard OpenAI-compatible client."""
    # Ensure key is present and clean
    api_key = (settings.groq_api_key or "").strip().strip('"').strip("'")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not configured or invalid")

    client = AsyncGroq(api_key=api_key)
    try:
        completion = await client.chat.completions.create(
            model=settings.groq_model,
            messages=messages,
            temperature=0.1,
            max_tokens=1024,
            timeout=timeout
        )
        return completion.choices[0].message.content or ""
    except Exception as exc:
        logger.error("Groq client fallback failed (%s): %s", type(exc).__name__, str(exc))
        raise DependencyServiceError(f"Failed to reach Groq: {exc}")

async def smart_llm_call(payload: dict[str, Any], system_prompt_text: str = None) -> str:
    """Calls local Ollama with a timeout, falling back to Groq if it takes too long."""
    ollama_timeout = settings.llm_fallback_timeout_seconds
    
    try:
        # Try local Ollama first with a strict timeout for fallback
        response = await call_ollama(payload, timeout=ollama_timeout)
        content = response.get("message", {}).get("content") or ""
        if content:
            return content
    except Exception as exc:
        # Catch both timeouts and connection errors to trigger fallback
        is_timeout = isinstance(exc, (asyncio.TimeoutError, httpx.TimeoutException)) or "timeout" in str(exc).lower()
        
        # Check if we can fallback to Groq
        api_key = (settings.groq_api_key or "").strip().strip('"').strip("'")
        if api_key:
            logger.warning("Local LLM failed or slow (%s), falling back to Groq...", type(exc).__name__)
            # Reconstruct messages for Groq (OpenAI format)
            groq_messages = []
            if system_prompt_text:
                groq_messages.append({"role": "system", "content": system_prompt_text})
            
            # Extract user messages from Ollama payload
            for msg in payload.get("messages", []):
                if msg.get("role") != "system":
                    groq_messages.append({"role": msg["role"], "content": msg["content"]})
            
            return await call_groq(groq_messages)
        else:
            # If no Groq, just wait longer for Ollama if it was a timeout, or re-raise
            if is_timeout:
                logger.info("No Groq key, waiting longer for Ollama...")
                response = await call_ollama(payload, timeout=settings.llm_timeout_seconds)
                return response.get("message", {}).get("content") or ""
            raise exc
            
    return ""

async def build_query_plan(message: str, history: list[dict[str, Any]] | None = None) -> QueryPlan:
    history_context = ""
    if history:
        history_context = "Cronologia recente:\n" + "\n".join(
            f"U: {h.get('message')}\nB: {h.get('answer')}" for h in history[-3:]
        ) + "\n\n"

    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "user", "content": f"{QUERY_PLAN_SYSTEM_PROMPT}\n\n{history_context}Domanda utente: {message}"},
        ],
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 420,
        },
    }

    try:
        content = await smart_llm_call(payload, system_prompt_text=QUERY_PLAN_SYSTEM_PROMPT)
        plan_data = parse_json_object(content)
        
        return QueryPlan(
            original_query=message,
            retrieval_query=message,
            domain=normalize_domains(plan_data.get("domains", []), "general")[0],
            filters=[],
            expanded_queries=[message],
            intent=normalize_intent(plan_data.get("intent", "general_information")),
            domains=normalize_domains(plan_data.get("domains", []), "general"),
            retrieval_queries=parse_retrieval_queries(
                plan_data.get("retrieval_queries"), message, ["general"]
            ),
            entities=normalized_entities(plan_data.get("entities", {})),
            response_language=normalize_language_code(plan_data.get("response_language", "it")),
            needs_clarification=bool(plan_data.get("needs_clarification", False)),
            clarification_question=optional_string(plan_data.get("clarification_question")),
        )
    except Exception as exc:
        logger.warning("query_plan_fallback error=%s", exc)
        return fallback_query_plan(message)


def fallback_query_plan(message: str) -> QueryPlan:
    return QueryPlan(
        original_query=message,
        retrieval_query=message,
        domain="general",
        filters=[],
        expanded_queries=[message],
        intent="general_information",
        domains=["general"],
        retrieval_queries=[PlannedRetrievalQuery(query=message, domain=None, weight=1.0)],
        entities={k: None for k in ENTITY_KEYS},
        response_language="it",
        needs_clarification=False,
    )


async def generate_grounded_answer(prompt: str, language_code: str) -> str:
    language_name = response_language_name(language_code)
    
    current_system_instruction = (
        f"Sei TARA, l'assistente ufficiale dei Giochi del Mediterraneo Taranto 2026.\n"
        f"REGOLE ASSOLUTE:\n"
        f"1. Rispondi ESCLUSIVAMENTE con le informazioni fornite nel CONTESTO sotto. NON usare conoscenze personali o esterne.\n"
        f"2. PROIBIZIONE TOTALE: NON fornire mai informazioni su trasporti, bus, pullman, linee urbane o fermate, anche se presenti nel contesto.\n"
        f"3. Se nel contesto si parla di una MASCOTTE (Ionios), e la descrizione visiva riporta un animale marino stilizzato o colorato, CONFERMA che si tratta di Ionios. NON dire che è un delfino o altro se non è scritto nel contesto.\n"
        f"4. Se l'informazione non è nel contesto, dì chiaramente che non lo sai.\n"
        f"5. Rispondi SOLO in {language_name}.\n"
        f"6. NON USARE MAI asterischi (**), grassetto o corsivo. Scrivi solo testo semplice."
    )
    
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "user", "content": f"{current_system_instruction}\n\n{prompt}"},
        ],
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 2048,
            "num_ctx": 8192,
        },
    }
    
    raw_answer = await smart_llm_call(payload, system_prompt_text=current_system_instruction)
    
    if not raw_answer:
        return unavailable_answer(language_code)
        
    answer = strip_thinking(raw_answer).strip()
    return strip_markdown(answer) or strip_markdown(raw_answer.strip())


async def build_answer(
    message: str,
    plan: QueryPlan,
    contexts: list[RetrievedContext],
    should_escalate: bool,
    reason: str | None,
    history: list[dict[Any]] | None = None,
) -> str:
    if explicit_operator_requested(message) or reason == "human_operator_requested":
        return human_operator_answer(plan.response_language)
        
    if not contexts:
        return unavailable_answer(plan.response_language)
    
    if should_escalate and reason in {
        "urgent_request",
        "live_data_unavailable",
        "complaint_or_lost_item",
    }:
        return unavailable_answer(plan.response_language)
        
    if plan.domain == "ticketing" and set(plan.domains).issubset({"ticketing", "general"}):
        answer = ticketing_guardrail_answer(plan.response_language)
    else:
        prompt = build_user_prompt(message, plan, contexts, history)
        answer = await generate_grounded_answer(prompt, plan.response_language)

    return clean_answer_text(answer)


def explicit_operator_requested(message: str) -> bool:
    normalized = normalize_text(message)
    if "operat" in normalized:
        return True
    human_keywords = ("umano", "persone", "persona", "umano", "esperto", "assistenza", "human", "person", "expert", "support", "real person")
    if any(k in normalized for k in human_keywords):
        return True
    return False


def is_refusal_answer(answer: str) -> bool:
    normalized = normalize_text(answer)
    refusal_keywords = [
        "informazioni sufficienti", 
        "non ho informazioni", 
        "i don't have enough information",
        "non posso rispondere",
        "inserisci l'email",
        "enter your email",
        "verrai ricontattato da un operatore"
    ]
    return any(kw in normalized for kw in refusal_keywords)


def human_operator_answer(response_language: str = "it") -> str:
    answers = {
        "it": "Certo, inserisci l'email qui sotto nella casella di testo e verrai ricontattato da un operatore umano il prima possibile.",
        "en": "Sure, enter your email in the text box below and you will be contacted by a human operator as soon as possible.",
        "es": "Claro, ingresa tu correo electrónico in il quadro di testo a continuación e un operatore umano si metterà in contatto con te il prima possibile.",
        "fr": "Bien sûr, saisissez votre e-mail nella zone de texte ci-dessous et vous serez contacté par un opérateur humain dès que possible.",
        "ar": "بالتأكيد، أدخل بريدك الإلكتروني in مربع النص أدناه وسيتصل بك موظف بشري in أقرب وقت ممکن."
    }
    lang = normalize_language_code(response_language)
    return answers.get(lang, answers["it"])


def unavailable_answer(response_language: str = "it") -> str:
    answers = {
        "it": "Al momento non ho un dato abbastanza preciso per risponderti con sicurezza. Posso indicarti il canale ufficiale o preparare una richiesta per un operatore.",
        "en": "I don't have enough precise information to answer you with certainty right now. I can direct you to the official channel or prepare a request for an operator.",
        "es": "No tengo informazioni sufficientemente precisa para responderte con sicurezza in questo momento. Puedo dirigirte al canal oficial o preparar una solicitud para un operador.",
        "fr": "Je n'ai pas d'informations suffisamment précises pour vous rispondere avec certitude pour le moment. Je peux vous diriger vers le canal officiel ou préparer una demande pour un opérateur.",
        "ar": "ليس لدي معلومات دقيقة كافية للإجابة عليك بيقين in الوقت الحالي. يمكنني توجيهك إلى القناة الرسمية أو إعداد طلب لموظف."
    }
    lang = normalize_language_code(response_language)
    return answers.get(lang, answers["it"])


def ticketing_guardrail_answer(response_language: str = "it") -> str:
    answer = (
        "Al momento i biglietti per Taranto 2026 non risultano ancora disponibili. "
        "Non sono ancora pubblicati ufficialmente prezzi, canali di acquisto, "
        "disponibilita o distinzione tra eventi gratuiti e a pagamento."
    )
    return translate_static_answer(answer, response_language)


def build_user_prompt(
    message: str,
    plan: QueryPlan,
    contexts: list[RetrievedContext],
    history: list[dict[str, Any]] | None = None,
) -> str:
    context_text = "\n\n".join([f"FONTE: {c.document}" for c in contexts])
    
    prompt = f"""
    CONTESTO DA USARE:
    {context_text}
    
    DOMANDA: {message}
    
    ISTRUZIONE: Rispondi alla domanda dell'utente in modo esauriente e completo usando SOLO il contesto sopra. 
    Includi tutti i dettagli rilevanti presenti nelle fonti (date, orari, curiosità, nomi completi) per fornire la migliore assistenza possibile.
    Se non trovi la risposta, ammetti di non saperlo.
    
    REGOLE DI STILE:
    - Rispondi solo alla domanda, NON aggiungere frasi come 'Non è presente alcun riferimento a...' o 'Non so altro su...'.
    - NON riportare coordinate geografiche (latitudine/longitudine) nel testo.
    - NON scrivere indirizzi lunghi o codici tecnici se non richiesti esplicitamente. 
    - L'utente ha a disposizione un'icona interattiva per vedere il luogo sulla mappa, quindi limitati al nome della struttura e della città.
    - NON USARE MAI GRASSETTO O ASTERISCHI.
    """
    return prompt


def clean_answer_text(answer: str) -> str:
    return answer.strip()


def parse_json_object(json_str: str) -> dict[str, Any]:
    json_str = json_str.strip()
    if json_str.startswith("```json"):
        json_str = json_str[7:]
    if json_str.endswith("```"):
        json_str = json_str[:-3]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", json_str, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        return {}


def strip_thinking(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return text

def strip_markdown(text: str) -> str:
    """Hard removal of markdown markers like asterisks, but keeps structure like headers or dashes."""
    return text.replace("**", "").replace("*", "").replace("__", "").replace("_", "")


def normalize_language_code(code: str) -> str:
    if not code: return "it"
    code = code.lower()[:2]
    return code if code in LANGUAGE_NAMES else "it"


def response_language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code.lower(), "Italiano")


def optional_string(value: Any) -> str | None:
    if not value: return None
    return str(value).strip() or None


def normalize_text(text: str) -> str:
    if not text: return ""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower().strip()        


def normalize_intent(intent: str) -> str:
    if intent in VALID_INTENTS:
        return intent
    return "general_information"


def normalize_domains(domains: list[str], default: str) -> list[str]:
    valid = [d for d in domains if d in VALID_DOMAINS]
    return valid if valid else [default]


def normalized_entities(entities: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in entities.items() if k in ENTITY_KEYS}

def detect_message_language(message: str, fallback: str = "it") -> str:
    return normalize_language_code(fallback)


def normalize_required_message(value: str) -> str:
    message = str(value or "").strip()
    if not message:
        raise ValidationServiceError("Message cannot be empty.")
    return message

async def translate_text(text: str, target_lang: str = "it") -> str:
    """Translates text to the target language using the LLM with fallback."""
    if not text or not text.strip():
        return text
        
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "user", "content": f"Traduci il testo in {LANGUAGE_NAMES.get(target_lang, 'Italiano')}. Rispondi SOLO con la traduzione.\n\nTesto: {text}"}
        ],
        "stream": False,
        "options": {"temperature": 0}
    }
    try:
        content = await smart_llm_call(payload)
        return strip_thinking(content).strip()
    except Exception as exc:
        logger.warning("Translation failed: %s", exc)
        return text

async def generate_conversation_summary(messages: list[dict[str, Any]]) -> str:
    """Generates a concise summary of the conversation with fallback."""
    if not messages:
        return "Nessuna conversazione."
        
    history_text = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "user", "content": f"Riassumi in italiano la chat (max 2 frasi):\n\n{history_text}"}
        ],
        "stream": False,
        "options": {"temperature": 0}
    }
    try:
        content = await smart_llm_call(payload)
        return strip_thinking(content).strip()
    except Exception as exc:
        logger.warning("Summary generation failed: %s", exc)
        return "Impossibile generare riassunto."
