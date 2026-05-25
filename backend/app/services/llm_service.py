import logging
import re
import time
from typing import Any, Dict, List, Optional
from functools import lru_cache

from backend.app.config import settings
from backend.app.repositories.persistence_repository import save_bot_message
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
from backend.app.services.chat_service import build_ticket_draft, ChatRequestDTO, ChatResponseDTO, SourceDTO, TicketDraftDTO
from backend.app.repositories.rag_repository import load_jsonl
from backend.app.repositories.database import get_transport_details, get_transport_routes, get_transport_calendar
from backend.app.services.rag_service import parse_retrieval_queries, translate_static_answer

logger = logging.getLogger(__name__)


def build_query_plan(message: str, history: list[dict[str, Any]] | None = None) -> QueryPlan:
    history_context = ""
    if history:
        history_context = "Cronologia recente:\n" + "\n".join(
            f"U: {h.get('message')}\nB: {h.get('answer')}" for h in history[-3:]
        ) + "\n\n"

    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": QUERY_PLAN_SYSTEM_PROMPT},
            {"role": "user", "content": f"{history_context}Domanda utente: {message}"},
        ],
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0,
            "num_predict": max(settings.query_parser_num_predict, 1024),
        },
    }

    try:
        response = call_ollama(payload)
        content = response.get("message", {}).get("content") or response.get("response")
        plan_data = parse_json_object(content)
        
        return QueryPlan(
            original_query=message,
            retrieval_query=message,
            domain=normalize_domains(plan_data.get("domains"), "general")[0],
            filters=[],
            expanded_queries=[message],
            intent=normalize_intent(plan_data.get("intent")),
            domains=normalize_domains(plan_data.get("domains"), "general"),
            retrieval_queries=parse_retrieval_queries(
                plan_data.get("retrieval_queries"), message, ["general"]
            ),
            entities=normalized_entities(plan_data.get("entities")),
            response_language=normalize_language_code(plan_data.get("response_language")),
            needs_clarification=bool(plan_data.get("needs_clarification")),
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


def generate_grounded_answer(prompt: str, language_code: str) -> str:
    language_name = response_language_name(language_code)
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Sei TARA, l'assistente virtuale ufficiale dei Giochi del Mediterraneo Taranto 2026. "
                    "Il tuo tono è professionale, accogliente e preciso. "
                    f"Rispondi ESCLUSIVAMENTE in lingua {language_name}."
                ),
            },
            {
                "role": "user",
                "content": f"Lingua risposta obbligatoria: {language_name}\n\n{prompt}",
            },
        ],
        "stream": False,
        "think": False,
        "options": {
            "temperature": settings.llm_temperature,
            "num_predict": settings.llm_num_predict,
            "num_ctx": settings.llm_context_window,
        },
    }
    response = call_ollama(payload, timeout=max(settings.llm_timeout_seconds, 150))
    answer = response.get("message", {}).get("content") or response.get("response")
    if not answer:
        raise DependencyServiceError("Ollama returned an empty response.")
    return strip_thinking(answer).strip()


def build_answer(
    message: str,
    plan: QueryPlan,
    contexts: list[RetrievedContext],
    should_escalate: bool,
    reason: str | None,
    history: list[dict[str, Any]] | None = None,
) -> str:
    # CASE 1: Explicit operator request
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
        logger.info("FINAL PROMPT:\n%s", prompt)
        answer = generate_grounded_answer(prompt, plan.response_language)
        answer = ensure_calendar_completeness(answer, message, plan, contexts)
        answer = enforce_ticketing_guardrail(answer, plan, contexts)

    return clean_answer_text(answer)


def explicit_operator_requested(message: str) -> bool:
    normalized = normalize_text(message)
    
    # CASE 1: Keyword "operat" (catches operatore, operatori, operator, operators)
    if "operat" in normalized:
        # Check if it's accompanied by a verb or intent to talk in IT or EN
        actions = ("parl", "voglio", "contatt", "sentir", "paral", "chiedere", "necessit", "serve", "posso", 
                   "speak", "talk", "want", "contact", "need", "can", "could")
        if any(a in normalized for a in actions):
            return True
        # Short phrases
        if len(normalized.split()) <= 3:
            return True

    # CASE 2: Other human-related requests (IT/EN)
    human_keywords = ("umano", "persone", "persona", "umano", "esperto", "assistenza", "human", "person", "expert", "support", "real person")
    if any(k in normalized for k in human_keywords):
        actions = ("parl", "voglio", "contatt", "sentir", "paral", "chiedere", "necessit", "serve", "posso",
                   "speak", "talk", "want", "contact", "need", "can", "could")
        if any(a in normalized for a in actions):
            return True

    return False


def is_refusal_answer(answer: str) -> bool:
    normalized = normalize_text(answer)
    refusal_keywords = [
        "informazioni sufficienti", 
        "dato abbastanza preciso", 
        "non ho informazioni", 
        "non risultano ancora disponibili",
        "non sono ancora pubblicati",
        "non dispongo di informazioni",
        "i don't have enough information",
        "enough precise information",
        "not available yet",
        "no tengo informacion",
        "no dispongo de informacion",
        "pas d'informations",
        "non ho un dato",
        "domanda non e specifica",
        "indica cosa desideri sapere",
        "per favore specifica",
        "non posso rispondere",
        "non ho dettagli",
        "servizio e riservato a comunicazioni civili",
        "posso rispondere solo a domande riguardanti i giochi",
        "inserisci l'email",
        "enter your email",
        "ingresa tu correo",
        "saisissez votre e-mail",
        "verrai ricontattato da un operatore",
        "contacted by a human operator",
        "operador humano se pondra en contacto",
        "contacte par un opérateur humain"
    ]
    return any(kw in normalized for kw in refusal_keywords)


def human_operator_answer(response_language: str = "it") -> str:
    # Hardcoded for reliability across common languages
    answers = {
        "it": "Certo, inserisci l'email qui sotto nella casella di testo e verrai ricontattato da un operatore umano il prima possibile.",
        "en": "Sure, enter your email in the text box below and you will be contacted by a human operator as soon as possible.",
        "es": "Claro, ingresa tu correo electrónico en el cuadro de texto a continuación y un operador humano se pondrá en contacto contigo lo antes posible.",
        "fr": "Bien sûr, saisissez votre e-mail dans la zone de texte ci-dessous et vous serez contacté par un opérateur humain dès que possible.",
        "ar": "بالتأكيد، أدخل بريدك الإلكتروني في مربع النص أدناه وسيتصل بك موظف بشري في أقرب وقت ممكن."
    }
    lang = normalize_language_code(response_language)
    return answers.get(lang, answers["it"])


def unavailable_answer(response_language: str = "it") -> str:
    answers = {
        "it": "Al momento non ho un dato abbastanza preciso per risponderti con sicurezza. Posso indicarti il canale ufficiale o preparare una richiesta per un operatore.",
        "en": "I don't have enough precise information to answer you with certainty right now. I can direct you to the official channel or prepare a request for an operator.",
        "es": "No tengo información suficientemente precisa para responderte con seguridad en este momento. Puedo dirigirte al canal oficial o preparar una solicitud para un operador.",
        "fr": "Je n'ai pas d'informations suffisamment précises pour vous répondre avec certitude pour le moment. Je peux vous diriger vers le canal officiel ou préparer une demande pour un opérateur.",
        "ar": "ليس لدي معلومات دقيقة كافية للإجابة عليك بيقين في الوقت الحالي. يمكنني توجيهك إلى القناة الرسمية أو إعداد طلب لموظف."
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
    structured_data = get_transport_details(plan.original_query)
    combined_data = {
        "structured": structured_data,
        "unstructured": contexts
    }
    
    prompt = f"""
    Rispondi ESCLUSIVAMENTE ai seguenti dati strutturati e non strutturati:
    
    Dati strutturati (da database):
    {json.dumps(structured_data, indent=2)}
    
    Contesto non strutturato (da RAG):
    {json.dumps([context.model_dump() for context in contexts], indent=2)}
    
    Domanda utente: {message}
    Piano di ricerca: {plan.model_dump()}
    
    Rispondi in {plan.response_language} basandoti SOLO sui dati forniti. Non inventare informazioni.
    """
    
    return prompt


def ensure_calendar_completeness(answer: str, message: str, plan: QueryPlan, contexts: list[RetrievedContext]) -> str:
    # Add calendar completeness check logic here
    return answer


def enforce_ticketing_guardrail(answer: str, plan: QueryPlan, contexts: list[RetrievedContext]) -> str:
    # Add ticketing guardrail logic here
    return answer


def clean_answer_text(answer: str) -> str:
    # Add answer cleaning logic here
    return answer


def parse_json_object(json_str: str) -> dict[str, Any]:
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc


def call_ollama(payload: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    req = Request("http://localhost:11434/api/generate", data=json.dumps(payload).encode(), headers=headers)
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode())


def strip_thinking(text: str) -> str:
    # Remove thinking markers like "Okay, let's see..." from the response
    return re.sub(r"^\s*Okay, let's see.*\n", "", text, flags=re.MULTILINE)


def normalize_language_code(code: str) -> str:
    return code.lower()


def response_language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code.lower(), "Italiano")


def optional_string(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def normalize_text(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").strip()


def language_score(tokens: set[str], normalized: str, markers: set[str]) -> int:
    score = sum(1 for token in tokens if token in normalized)
    score += sum(2 for marker in markers if " " in marker and marker in normalized)
    return score


def normalize_intent(intent: str) -> str:
    if intent in VALID_INTENTS:
        return intent
    return "general_information"


def normalize_domains(domains: list[str], default: str) -> list[str]:
    return [d for d in domains if d in VALID_DOMAINS] or [default]


def normalized_entities(entities: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in entities.items() if k in ENTITY_KEYS}


def get_transport_details(stop_id: str) -> dict[str, Any]:
    query = """
        SELECT 
            t.stop_id,
            t.stop_name,
            t.stop_lat,
            t.stop_lon,
            t.stop_desc,
            ts.arrival_time,
            ts.departure_time,
            tr.route_short_name,
            tr.route_long_name,
            tr.route_type,
            ta.agency_name,
            ta.agency_url,
            tc.service_id,
            tc.start_date,
            tc.end
    """
    result = fetch_all(query, (stop_id,))
    return result


def get_transport_routes() -> list[dict[str, Any]]:
    query = """
        SELECT 
            route_id,
            route_short_name,
            route_long_name,
            route_type,
            agency_id,
            agency_name
        FROM transport_routes
        JOIN transport_agency ON transport_routes.agency_id = transport_agency.agency_id
        ORDER BY route_type, route_short_name
    """
    return fetch_all(query)


def get_transport_calendar(service_id: str) -> dict[str, Any]:
    query = """
        SELECT 
            service_id,
            monday,
            tuesday,
            wednesday,
            thursday,
            friday,
            saturday,
            sunday,
            start_date,
            end_date
        FROM transport_calendar
        WHERE service_id = %s
    """
    result = fetch_one(query, (service_id,))
    return result


def get_transport_calendar_dates(service_id: str) -> list[dict[str, Any]]:
    query = """
        SELECT 
            service_id,
            date,
            exception_type
        FROM transport_calendar_dates
        WHERE service_id = %s
        ORDER BY date
    """
    return fetch_all(query, (service_id,))
