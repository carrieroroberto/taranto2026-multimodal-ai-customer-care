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
from backend.app.services.rag_service import parse_retrieval_queries
from groq import AsyncGroq

logger = logging.getLogger(__name__)

QUERY_PLAN_SYSTEM_PROMPT = """Sei il Query Planner LLM di TALOS per i Giochi del Mediterraneo Taranto 2026.
Devi restituire solo JSON valido, senza markdown e senza spiegazioni.

Compiti:
- rileva la lingua effettiva del messaggio utente tra: it, en, es, fr, ar;
- la lingua va rilevata da zero sul messaggio corrente: NON copiarla dalla lingua UI e NON copiarla dalla cronologia;
- se il messaggio corrente e' chiaramente in una delle lingue supportate, usa quella lingua anche se la UI corrente e' diversa;
- usa la lingua UI corrente solo se il messaggio e' ambiguo, troppo corto o in una lingua non supportata;
- se il messaggio e' composto da caratteri casuali, sigle senza significato o testo non interpretabile, language deve essere la lingua UI corrente;
- traduci semanticamente la richiesta in italiano per la ricerca nella knowledge base;
- correggi refusi evidenti;
- produci query di retrieval sempre in italiano;
- non inventare fatti, date, prezzi, sedi, link o risultati.
- se non riesci a capire la richiesta, non ripetere e non citare mai il testo originale dell'utente nella risposta finale.

Schema JSON obbligatorio:
{
  "language": "it|en|es|fr|ar",
  "intent": "general_information|ticketing|venue_information|calendar|volunteering|accessibility",
  "domains": ["general|ticketing|venue|calendar|volunteering|accessibility"],
  "query_it": "richiesta tradotta e normalizzata in italiano",
  "entities": {
    "sport": null,
    "venue": null,
    "atleta": null,
    "data": null
  },
  "retrieval_queries": [
    {"query": "query in italiano", "domain": "general|ticketing|venue|calendar|volunteering|accessibility|null", "weight": 1.0}
  ],
  "needs_clarification": false,
  "clarification_question": null
}

Regole:
- massimo 4 retrieval_queries;
- language deve indicare la lingua in cui rispondere;
- query_it e retrieval_queries devono essere in italiano anche se il messaggio utente e' in inglese, spagnolo, francese o arabo.

Esempi di rilevamento:
- "Where can I buy tickets?" => language "en", query_it "Dove posso comprare i biglietti?"
- "Donde se celebra la ceremonia de apertura?" => language "es", query_it "Dove si svolge la cerimonia di apertura?"
- "Je veux savoir si les billets sont gratuits" => language "fr", query_it "Voglio sapere se i biglietti sono gratuiti"
- "متى تبدأ الألعاب؟" => language "ar", query_it "Quando iniziano i Giochi?"
- "Quando iniziano i Giochi?" => language "it", query_it "Quando iniziano i Giochi?"
"""

FALLBACK_LANGUAGE_QUERY_PROMPT = """Analizza il messaggio utente e restituisci solo JSON valido.
Devi rilevare la lingua del messaggio corrente tra it, en, es, fr, ar e produrre la query italiana per il retrieval.
Non usare la lingua UI se il messaggio corrente e' chiaramente in una lingua supportata.
Usa la lingua UI solo se il messaggio e' ambiguo o in lingua non supportata.
Se il messaggio e' composto da caratteri casuali o testo non interpretabile, usa la lingua UI corrente.

Schema:
{
  "language": "it|en|es|fr|ar",
  "query_it": "messaggio tradotto e normalizzato in italiano"
}
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
    api_key = (settings.groq_api_key or "").strip().strip('"').strip("'")

    if api_key and (settings.ai_disabled or ollama_timeout <= 0):
        logger.info("Groq key configured and local AI disabled or fallback timeout <= 0: skipping local Ollama.")
        return await call_groq(
            ollama_payload_to_groq_messages(payload, system_prompt_text),
            timeout=max(float(settings.llm_timeout_seconds), 30.0),
        )
    
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
        if api_key:
            logger.warning("Local LLM failed or slow (%s), falling back to Groq...", type(exc).__name__)
            return await call_groq(
                ollama_payload_to_groq_messages(payload, system_prompt_text),
                timeout=max(float(settings.llm_timeout_seconds), 30.0),
            )
        else:
            # If no Groq, just wait longer for Ollama if it was a timeout, or re-raise
            if is_timeout:
                logger.info("No Groq key, waiting longer for Ollama...")
                response = await call_ollama(payload, timeout=settings.llm_timeout_seconds)
                return response.get("message", {}).get("content") or ""
            raise exc
            
    return ""


def ollama_payload_to_groq_messages(
    payload: dict[str, Any],
    system_prompt_text: str | None = None,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []

    if system_prompt_text:
        messages.append({"role": "system", "content": system_prompt_text})

    for message in payload.get("messages", []):
        role = message.get("role") or "user"
        if role not in {"system", "user", "assistant"}:
            role = "user"
        if role == "system" and system_prompt_text:
            continue

        content = str(message.get("content") or "")
        if role == "user" and system_prompt_text and content.startswith(system_prompt_text):
            content = content[len(system_prompt_text):].lstrip()
        if content:
            messages.append({"role": role, "content": content})

    return messages or [{"role": "user", "content": ""}]

async def build_query_plan(
    message: str,
    history: list[dict[str, Any]] | None = None,
    ui_language: str = "it",
) -> QueryPlan:
    fallback_language = normalize_language_code(ui_language)
    language_is_ambiguous = is_language_ambiguous(message)
    history_context = ""
    if history:
        history_context = "Cronologia recente:\n" + "\n".join(
            f"U: {h.get('message')}\nB: {h.get('answer')}" for h in history[-3:]
        ) + "\n\n"

    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": QUERY_PLAN_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Lingua UI corrente: {fallback_language}\n"
                    f"{history_context}"
                    f"Domanda utente: {message}"
                ),
            },
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
        if not plan_data:
            raise ValueError("Query planner returned empty JSON.")
        response_language = normalize_language_code(
            plan_data.get("language")
            or plan_data.get("response_language")
            or fallback_language,
            fallback_language,
        )
        if language_is_ambiguous:
            response_language = fallback_language
        domains = normalize_domains(plan_data.get("domains", []), "general")
        query_it = first_non_empty(
            plan_data.get("query_it"),
            plan_data.get("normalized_query"),
            plan_data.get("retrieval_query"),
        )
        if not query_it:
            raise ValueError("Query planner did not return query_it.")
        expanded_queries = italian_query_list(plan_data.get("expanded_queries"), query_it)
        retrieval_queries = parse_retrieval_queries(
            plan_data.get("retrieval_queries"), query_it, domains
        )
        
        return QueryPlan(
            original_query=message,
            retrieval_query=query_it,
            domain=domains[0],
            filters=string_list(plan_data.get("filters")),
            expanded_queries=expanded_queries,
            intent=normalize_intent(plan_data.get("intent", "general_information")),
            domains=domains,
            retrieval_queries=retrieval_queries,
            entities=normalized_entities(plan_data.get("entities", {})),
            response_language=response_language,
            needs_clarification=bool(plan_data.get("needs_clarification", False)),
            clarification_question=optional_string(plan_data.get("clarification_question")),
            language_detected=not language_is_ambiguous,
        )
    except Exception as exc:
        logger.warning("query_plan_fallback error=%s", exc)
        fallback_query, detected_language = await fallback_query_analysis(message, fallback_language)
        if language_is_ambiguous:
            detected_language = fallback_language
        return fallback_query_plan(
            message,
            fallback_query,
            detected_language,
            language_detected=not language_is_ambiguous,
        )


def fallback_query_plan(
    message: str,
    retrieval_query: str | None = None,
    response_language: str = "it",
    language_detected: bool = True,
) -> QueryPlan:
    query_it = (retrieval_query or message).strip() or message
    return QueryPlan(
        original_query=message,
        retrieval_query=query_it,
        domain="general",
        filters=[],
        expanded_queries=[query_it],
        intent="general_information",
        domains=["general"],
        retrieval_queries=[PlannedRetrievalQuery(query=query_it, domain=None, weight=1.0)],
        entities={k: None for k in ENTITY_KEYS},
        response_language=normalize_language_code(response_language),
        needs_clarification=False,
        language_detected=language_detected,
    )


async def generate_grounded_answer(prompt: str, language_code: str) -> str:
    language_name = response_language_name(language_code)
    
    current_system_instruction = (
        f"Sei TALOS, l'assistente ufficiale dei Giochi del Mediterraneo Taranto 2026.\n"
        f"REGOLE ASSOLUTE:\n"
        f"1. Rispondi ESCLUSIVAMENTE con le informazioni fornite nel CONTESTO sotto. NON usare conoscenze personali o esterne.\n"
        f"2. PROIBIZIONE TOTALE: NON fornire mai informazioni su trasporti, bus, pullman, linee urbane o fermate, anche se presenti nel contesto.\n"
        f"3. Se nel contesto si parla di una MASCOTTE (Ionios), e la descrizione visiva riporta un animale marino stilizzato o colorato, CONFERMA che si tratta di Ionios. NON dire che è un delfino o altro se non è scritto nel contesto.\n"
        f"4. Se l'informazione non è nel contesto, non puoi rispondere ma scusati a tal proposito e NON ripetere messaggio e parole contenute in esso scritte dall'utente.\n"
        f"5. Rispondi SOLO in {language_name}.\n"
        f"6. NON USARE MAI asterischi (**), grassetto o corsivo. Scrivi solo testo semplice.\n"
        f"7. Se non capisci la richiesta o non trovi dati utili, non ripetere e non citare mai il testo dell'utente.\n"
        f"8. Il tuo nome e' TALOS. Se ti viene chiesto chi sei, come ti chiami o qualcosa del genere, rispondi TALOS."
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
    visual_context: str | None = None,
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
        prompt = build_user_prompt(message, plan, contexts, history, visual_context)
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
        "non so",
        "non lo so",
        "non capisco",
        "non ho capito",
        "non riesco a capire",
        "non riesco a comprendere",
        "potresti riformulare",
        "puoi riformulare",
        "fornire piu contesto",
        "informazioni sufficienti", 
        "non ho informazioni", 
        "non ho trovato",
        "i don t know",
        "i don't know",
        "i don't have enough information",
        "could not find",
        "couldn't find",
        "do not understand",
        "don't understand",
        "please rephrase",
        "provide more context",
        "no lo se",
        "no entiendo",
        "no he entendido",
        "puedes reformular",
        "podrias reformular",
        "je ne sais pas",
        "je ne comprends pas",
        "pourriez vous reformuler",
        "pouvez vous reformuler",
        "non posso rispondere",
        "inserisci l'email",
        "scrivi la tua email",
        "enter your email",
        "verrai ricontattato da un operatore"
    ]
    return any(kw in normalized for kw in refusal_keywords)


def answer_repeats_user_text(answer: str, message: str) -> bool:
    normalized_answer = normalize_text(answer)
    normalized_message = normalize_text(message)
    if not normalized_answer or not normalized_message:
        return False

    tokens = normalized_message.split()
    if len(tokens) < 2 or len(normalized_message) < 16:
        return False

    return normalized_message in normalized_answer


def human_operator_answer(response_language: str = "it") -> str:
    answers = {
        "it": "Certo, scrivi la tua email nella casella di testo e verrai ricontattato da un operatore umano il prima possibile.",
        "en": "Sure, write your email in the text box and you will be contacted by a human operator as soon as possible.",
        "es": "Claro, escribe tu correo electrónico en el cuadro de texto y un operador humano se pondrá en contacto contigo lo antes posible.",
        "fr": "Bien sûr, écrivez votre adresse e-mail dans la zone de texte et un opérateur humain vous recontactera dès que possible.",
        "ar": "بالتأكيد، اكتب بريدك الإلكتروني في مربع النص وسيتم التواصل معك من قبل موظف في أقرب وقت ممكن."
    }
    lang = normalize_language_code(response_language)
    return answers.get(lang, answers["it"])


def unavailable_answer(response_language: str = "it") -> str:
    answers = {
        "it": "Al momento non ho un dato abbastanza preciso per risponderti con sicurezza.",
        "en": "I don't have enough precise information to answer you with certainty right now.",
        "es": "No tengo información suficientemente precisa para responderte con seguridad en este momento.",
        "fr": "Je n'ai pas d'informations suffisamment précises pour vous répondre avec certitude pour le moment.",
        "ar": "لا أملك معلومات دقيقة بما يكفي للإجابة عليك بثقة في الوقت الحالي.",
    }
    lang = normalize_language_code(response_language)
    return answers.get(lang, answers["it"])


def ticketing_guardrail_answer(response_language: str = "it") -> str:
    answers = {
        "it": (
            "Al momento i biglietti per Taranto 2026 non risultano ancora disponibili. "
            "Non sono ancora pubblicati ufficialmente prezzi, canali di acquisto, "
            "disponibilita o distinzione tra eventi gratuiti e a pagamento."
        ),
        "en": (
            "Tickets for Taranto 2026 are not available yet. Official prices, "
            "purchase channels, availability and the distinction between free and paid events "
            "have not been published yet."
        ),
        "es": (
            "Las entradas para Taranto 2026 aun no estan disponibles. Todavia no se han publicado "
            "precios oficiales, canales de compra, disponibilidad ni la distincion entre eventos "
            "gratuitos y de pago."
        ),
        "fr": (
            "Les billets pour Taranto 2026 ne sont pas encore disponibles. Les prix officiels, "
            "les canaux d'achat, la disponibilite et la distinction entre evenements gratuits "
            "et payants n'ont pas encore ete publies."
        ),
        "ar": (
            "تذاكر تارانتو 2026 غير متاحة بعد. لم يتم نشر الأسعار الرسمية أو قنوات الشراء "
            "أو التوفر أو التمييز بين الفعاليات المجانية والمدفوعة حتى الآن."
        ),
    }
    lang = normalize_language_code(response_language)
    return answers.get(lang, answers["it"])


def build_user_prompt(
    message: str,
    plan: QueryPlan,
    contexts: list[RetrievedContext],
    history: list[dict[str, Any]] | None = None,
    visual_context: str | None = None,
) -> str:
    context_text = "\n\n".join([f"FONTE: {c.document}" for c in contexts])
    visual_block = ""
    if visual_context:
        visual_block = f"""
    CONTESTO VISIVO FORNITO DALL'IMMAGINE:
    {visual_context.strip()}

    REGOLA MULTIMODALE:
    L'immagine e' il riferimento principale della richiesta. Interpreta il testo dell'utente come focus o domanda sull'immagine, non come richiesta separata.
    """
    
    prompt = f"""
    CONTESTO DA USARE:
    {context_text}
    {visual_block}
    
    DOMANDA: {message}
    
    ISTRUZIONE: Rispondi alla domanda dell'utente in modo esauriente e completo usando SOLO il contesto sopra. 
    Includi tutti i dettagli rilevanti presenti nelle fonti (date, orari, curiosità, nomi completi) per fornire la migliore assistenza possibile.
    Se non trovi la risposta, ammetti di non saperlo, ma NON ripetere le parole e il messaggio dell'utente.
    
    REGOLE DI STILE:
    - Rispondi solo alla domanda, se non capisci non ripetere mai il messaggio dell'utente perchè può contenere testo scurrile o volgare. In tal caso NON aggiungere frasi come 'Non è presente alcun riferimento a...' o 'Non so altro su...'.
    - NON riportare coordinate geografiche (latitudine/longitudine) nel testo.
    - NON scrivere indirizzi lunghi o codici tecnici se non richiesti esplicitamente. 
    - L'utente ha a disposizione un'icona interattiva per vedere il luogo sulla mappa, quindi limitati al nome della struttura e della città.
    - NON USARE MAI GRASSETTO O ASTERISCHI.
    """
    return prompt


def clean_answer_text(answer: str) -> str:
    text = (answer or "").strip()
    for legacy_name in ("T" + "ARA", "T" + "ara", "t" + "ara"):
        text = re.sub(rf"\b{re.escape(legacy_name)}\b", "TALOS", text)
    return text


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


def normalize_language_code(code: str | None, fallback: str = "it") -> str:
    fallback = (fallback or "it").lower()[:2]
    if fallback not in LANGUAGE_NAMES:
        fallback = "it"
    if not code:
        return fallback
    code = code.lower()[:2]
    return code if code in LANGUAGE_NAMES else fallback


def response_language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code.lower(), "Italiano")


def is_language_ambiguous(message: str) -> bool:
    text = str(message or "").strip()
    if not text:
        return True

    letters = [ch for ch in text if ch.isalpha()]
    if len(letters) < 3:
        return True

    # Script non latino leggibile: lasciamo che il planner gestisca la lingua.
    if re.search(r"[\u0600-\u06ff]", text):
        return False

    latin_tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]+", text)
    if not latin_tokens:
        return True

    token_count = len(latin_tokens)
    total_latin_letters = sum(len(token) for token in latin_tokens)
    vowels = sum(1 for ch in "".join(latin_tokens).lower() if ch in "aeiouàèéìòóùáíúü")
    vowel_ratio = vowels / max(total_latin_letters, 1)

    if token_count == 1 and total_latin_letters >= 5 and vowel_ratio < 0.22:
        return True

    if token_count <= 2 and total_latin_letters >= 8 and vowel_ratio < 0.18:
        return True

    return False


def optional_string(value: Any) -> str | None:
    if not value: return None
    return str(value).strip() or None


def first_non_empty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


def italian_query_list(value: Any, query_it: str) -> list[str]:
    queries = string_list(value)
    if query_it and query_it not in queries:
        queries.insert(0, query_it)
    return queries or [query_it]


async def fallback_retrieval_query_it(message: str) -> str:
    try:
        translated = await translate_text(message, "it")
        return translated.strip() or message
    except Exception as exc:
        logger.warning("fallback query translation failed: %s", exc)
        return message


async def fallback_query_analysis(message: str, ui_language: str) -> tuple[str, str]:
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": FALLBACK_LANGUAGE_QUERY_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Lingua UI corrente: {normalize_language_code(ui_language)}\n"
                    f"Messaggio utente: {message}"
                ),
            },
        ],
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 180,
        },
    }

    try:
        content = await smart_llm_call(payload, system_prompt_text=FALLBACK_LANGUAGE_QUERY_PROMPT)
        data = parse_json_object(content)
        language = normalize_language_code(data.get("language"), ui_language)
        query_it = first_non_empty(data.get("query_it"), data.get("italian_query"))
        if query_it:
            return query_it, language
    except Exception as exc:
        logger.warning("fallback language/query analysis failed: %s", exc)

    return await fallback_retrieval_query_it(message), normalize_language_code(ui_language)


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
            {
                "role": "user",
                "content": (
                    f"Traduci il testo in {LANGUAGE_NAMES.get(target_lang, 'Italiano')}.\n"
                    "Il testo puo essere in qualunque lingua; se e' gia nella lingua target, restituiscilo invariato.\n"
                    "Rispondi SOLO con il testo tradotto, senza etichette, senza introduzioni e senza markdown.\n\n"
                    f"Testo: {text}"
                ),
            }
        ],
        "stream": False,
        "options": {"temperature": 0, "num_predict": 700}
    }
    try:
        content = await smart_llm_call(payload)
        return strip_thinking(content).strip()
    except Exception as exc:
        logger.warning("Translation failed: %s", exc)
        return text

async def generate_conversation_summary(
    messages: list[dict[str, Any]],
    escalation_message: dict[str, Any] | None = None,
) -> str:
    """Generates a concise operator summary focused on the escalation trigger."""
    if not messages:
        return "Nessuna conversazione."

    escalation_text = clean_summary_message_text(
        str((escalation_message or {}).get("content") or "")
    )
    if not escalation_text:
        user_messages = [
            clean_summary_message_text(str(message.get("content") or ""))
            for message in messages
            if message.get("role") == "user"
        ]
        escalation_text = next((message for message in reversed(user_messages) if message), "")

    recent_messages = messages[-8:]
    history_text = "\n".join(
        f"{message.get('role', 'messaggio')}: {clean_summary_message_text(str(message.get('content') or ''))}"
        for message in recent_messages
        if clean_summary_message_text(str(message.get("content") or ""))
    )
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {
                "role": "user",
                "content": (
                    "Scrivi un summary operativo in italiano per un ticket customer-care.\n"
                    "Rispondi SOLO con il riassunto finale, senza introduzioni, senza frasi come "
                    "'Ecco un riassunto', senza markdown e senza preamboli.\n"
                    "Il riassunto deve concentrarsi soprattutto sul messaggio che ha generato "
                    "l'escalation; usa la cronologia solo come contesto secondario.\n"
                    "Massimo 2 frasi brevi.\n\n"
                    f"MESSAGGIO CHE HA GENERATO L'ESCALATION:\n{escalation_text}\n\n"
                    f"CRONOLOGIA RECENTE:\n{history_text}"
                ),
            }
        ],
        "stream": False,
        "options": {"temperature": 0, "num_predict": 220}
    }
    try:
        content = await smart_llm_call(payload)
        return clean_summary_response(strip_thinking(content).strip())
    except Exception as exc:
        logger.warning("Summary generation failed: %s", exc)
        return "Impossibile generare riassunto."


def clean_summary_response(text: str) -> str:
    summary = strip_markdown(text or "").strip()
    summary = re.sub(
        r"^(?:ecco\s+)?(?:un\s+)?riassunto(?:\s+della\s+chat)?(?:\s+in\s+italiano)?(?:\s+in\s+\d+\s+frasi?)?\s*[:\-]\s*",
        "",
        summary,
        flags=re.IGNORECASE,
    ).strip()
    summary = re.sub(
        r"^summary(?:\s+operativo)?\s*[:\-]\s*",
        "",
        summary,
        flags=re.IGNORECASE,
    ).strip()
    return summary


def clean_summary_message_text(content: str) -> str:
    text = re.sub(r"\[(?:IMAGE|AUDIO)_URL:[^\]]+\]", "", content or "")
    text = re.sub(r"Descrizione immagine:.*", "", text, flags=re.DOTALL)
    text = re.sub(r"Testo estratto dall'immagine:.*", "", text, flags=re.DOTALL)
    return re.sub(r"\s+", " ", text).strip()


async def translate_operator_conversation(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Translate readable conversation content to Italian for the operator dashboard."""
    translated_messages: list[dict[str, Any]] = []
    readable = []
    for index, message in enumerate(messages):
        content = operator_message_readable_text(message)
        if not content:
            translated_messages.append({**message, "translated_content": None})
            continue
        translated_messages.append({**message, "translated_content": content})
        readable.append((index, message.get("role", "messaggio"), content))

    if not readable:
        return translated_messages

    source_text = "\n".join(
        f"{idx}. {role}: {content}" for idx, role, content in readable
    )
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {
                "role": "user",
                "content": (
                    "Traduci in italiano i messaggi testuali della conversazione customer-care.\n"
                    "Ogni messaggio puo essere in una lingua diversa: rileva la lingua di ciascun messaggio in modo indipendente.\n"
                    "Traduci tutti i messaggi testuali in italiano; se un messaggio e' gia in italiano, restituiscilo invariato.\n"
                    "Non riassumere, non spiegare, non aggiungere note e non omettere messaggi.\n"
                    "Rispondi SOLO con JSON valido, senza markdown, nel formato:\n"
                    "{\"translations\":[{\"index\":0,\"text\":\"...\"}]}\n"
                    "Deve esserci esattamente un oggetto per ogni index ricevuto.\n"
                    "Mantieni invariati nomi, email, date, luoghi e sigle.\n\n"
                    f"MESSAGGI:\n{source_text}"
                ),
            }
        ],
        "stream": False,
        "options": {"temperature": 0, "num_predict": 2200},
    }

    try:
        content = await smart_llm_call(payload)
        data = parse_json_object(strip_thinking(content).strip())
        translations = data.get("translations") if isinstance(data, dict) else None
        if not isinstance(translations, list):
            return await translate_operator_conversation_items(translated_messages, readable)

        applied_indexes: set[int] = set()
        for item in translations:
            try:
                index = int(item.get("index"))
            except (TypeError, ValueError):
                continue
            text = str(item.get("text") or "").strip()
            if text and 0 <= index < len(translated_messages):
                translated_messages[index]["translated_content"] = text
                applied_indexes.add(index)
        if not applied_indexes:
            return await translate_operator_conversation_items(translated_messages, readable)
        missing_readable = [
            (index, role, content)
            for index, role, content in readable
            if index not in applied_indexes
        ]
        if missing_readable:
            return await translate_operator_conversation_items(
                translated_messages,
                missing_readable,
            )
    except Exception as exc:
        logger.warning("operator conversation translation failed: %s", exc)
        return await translate_operator_conversation_items(translated_messages, readable)

    return translated_messages


async def translate_operator_conversation_items(
    translated_messages: list[dict[str, Any]],
    readable: list[tuple[int, Any, str]],
) -> list[dict[str, Any]]:
    """Fallback translation path for operator conversations when JSON batch parsing fails."""
    for index, _role, content in readable:
        if not content or not 0 <= index < len(translated_messages):
            continue
        try:
            translated_messages[index]["translated_content"] = await translate_text(content, "it")
        except Exception as exc:
            logger.warning("operator message translation failed: %s", exc)
    return translated_messages


async def generate_operator_email_draft(
    ticket: dict[str, Any],
    operator: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Generate a concise email draft for the operator in the user's language."""
    user_email = str(ticket.get("user_email") or "").strip()
    operator_name = str((operator or {}).get("name") or "Operatore").strip() or "Operatore"
    ticket_code = str(ticket.get("id") or "").split("-")[0][:8] or "ticket"
    summary = str(ticket.get("summary") or "").strip()
    domain = str(ticket.get("domain") or "informazioni generali").strip()
    priority = str(ticket.get("priority") or "media").strip()
    conversation = ticket.get("conversation") or []
    readable_messages = [
        (message.get("role", "messaggio"), operator_message_readable_text(message))
        for message in conversation[-12:]
    ]
    conversation_text = "\n".join(
        f"{role}: {content}"
        for role, content in readable_messages
        if content
    )
    fallback_subject = f"T.A.L.O.S. - Risposta alla Richiesta di Supporto #{ticket_code}"
    fallback_body = build_operator_email_body(
        user_email,
        fallback_operator_email_specific_response(summary),
        operator_name,
    )

    payload = {
        "model": settings.ollama_model,
        "messages": [
            {
                "role": "user",
                "content": (
                    "Genera il testo personalizzato per una bozza email customer-care TALOS.\n"
                    "Rileva la lingua dell'utente dalla cronologia, dando priorita all'ultimo messaggio utente leggibile.\n"
                    "Scrivi il testo personalizzato nella stessa lingua dell'utente. Se la lingua non e' chiara, usa italiano.\n"
                    "Il testo deve essere personalizzato in base alla conversazione dando una possibile soluzione. NON nominare mai TALOS, l'utente, l'operatore, ma DEVI scrivere come se sei tu stesso l'operatore che sta rispondendo all'utente e non in terza persona. Rendi la risposta coerente per continuare il messaggio introduttivo e di apertura della mail.\n"
                    "Mantieni T.A.L.O.S. invariato e non tradurre il nome/acronimo.\n"
                    "Non includere saluti, oggetto, firma, markdown o template completo.\n"
                    "Non iniziare con formule equivalenti a 'In merito alla tua richiesta' o 'Regarding your request'.\n"
                    "Massimo 2 frasi.\n"
                    "Non inventare date, prezzi, link o informazioni non presenti.\n\n"
                    "Rispondi SOLO con JSON valido, senza markdown, nel formato:\n"
                    "{\"language\":\"it|en|es|fr|ar|other\",\"specific_response\":\"...\"}\n\n"
                    f"CODICE TICKET: {ticket_code}\n"
                    f"EMAIL UTENTE: {user_email}\n"
                    f"NOME OPERATORE: {operator_name}\n"
                    f"DOMINIO: {domain}\n"
                    f"PRIORITA: {priority}\n"
                    f"SUMMARY TICKET: {summary}\n"
                    f"CRONOLOGIA RECENTE:\n{conversation_text}"
                ),
            }
        ],
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 700},
    }

    try:
        content = await smart_llm_call(payload)
        data = parse_json_object(strip_thinking(content).strip())
        language = normalize_language_code(str(data.get("language") or ""), "it")
        subject = operator_email_subject_for_language(language, ticket_code)
        specific_response = clean_operator_email_specific_response(
            str(data.get("specific_response") or data.get("body") or "")
        )
        if subject and specific_response:
            body = build_operator_email_body_for_language(
                language,
                user_email,
                specific_response,
                operator_name,
            )
            return {"subject": subject, "body": body}
    except Exception as exc:
        logger.warning("operator email draft failed: %s", exc)

    return {
        "subject": fallback_subject,
        "body": fallback_body,
    }


def operator_message_readable_text(message: dict[str, Any]) -> str:
    message_type = str(message.get("type") or "text").strip().lower()
    content = clean_summary_message_text(str(message.get("content") or "")).strip()
    caption = clean_summary_message_text(str(message.get("caption") or "")).strip()
    if message_type == "image" and caption:
        return f"Messaggio con immagine - testo utente: {caption}"
    return content or caption


def operator_email_subject_for_language(language: str, ticket_code: str) -> str:
    code = ticket_code or "ticket"
    match normalize_language_code(language, "it"):
        case "en":
            return f"T.A.L.O.S. - Reply to Support Request #{code}"
        case "es":
            return f"T.A.L.O.S. - Respuesta a la Solicitud de Soporte #{code}"
        case "fr":
            return f"T.A.L.O.S. - Reponse a la Demande de Support #{code}"
        case "ar":
            return f"T.A.L.O.S. - رد على طلب الدعم #{code}"
        case _:
            return f"T.A.L.O.S. - Risposta alla Richiesta di Supporto #{code}"


def build_operator_email_body_for_language(
    language: str,
    user_email: str,
    specific_response: str,
    operator_name: str,
) -> str:
    normalized_language = normalize_language_code(language, "it")
    continuation = email_specific_continuation(specific_response, normalized_language)
    match normalized_language:
        case "en":
            return (
                f"Dear User ({user_email}),\n"
                "thank you for contacting T.A.L.O.S., your assistant for the 2026 Mediterranean Games in Taranto!\n\n"
                f"Regarding your request, {continuation}\n\n"
                "I remain available for any clarification or further questions!\n\n"
                "See you soon,\n"
                f"{operator_name}."
            )
        case "es":
            return (
                f"Estimado usuario ({user_email}),\n"
                "gracias por contactar con T.A.L.O.S., tu asistente para los Juegos Mediterraneos 2026 en Taranto!\n\n"
                f"Con respecto a tu solicitud, {continuation}\n\n"
                "Quedo a tu disposicion para cualquier aclaracion o pregunta adicional!\n\n"
                "Hasta pronto,\n"
                f"{operator_name}."
            )
        case "fr":
            return (
                f"Cher utilisateur ({user_email}),\n"
                "merci d'avoir contacte T.A.L.O.S., votre assistant pour les Jeux Mediterraneens 2026 a Tarente!\n\n"
                f"Concernant votre demande, {continuation}\n\n"
                "Je reste a votre disposition pour toute clarification ou question supplementaire!\n\n"
                "A bientot,\n"
                f"{operator_name}."
            )
        case "ar":
            return (
                f"عزيزي المستخدم ({user_email}),\n"
                "شكرًا لتواصلك مع T.A.L.O.S.، مساعدك لألعاب البحر الأبيض المتوسط 2026 في تارانتو!\n\n"
                f"بخصوص طلبك، {continuation}\n\n"
                "أبقى متاحًا لأي توضيحات أو أسئلة إضافية!\n\n"
                "إلى اللقاء قريبًا،\n"
                f"{operator_name}."
            )
        case _:
            return build_operator_email_body(user_email, specific_response, operator_name)


def clean_operator_email_body(body: str) -> str:
    cleaned = strip_markdown(body or "").strip().strip('"')
    cleaned = cleaned.replace("\\n", "\n")
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def fallback_operator_email_specific_response(summary: str) -> str:
    if summary:
        return (
            f"relativa a {summary}, la tua segnalazione e' stata presa in carico "
            "dal customer care e verra gestita sulla base delle informazioni disponibili."
        )
    return (
        "abbiamo preso in carico la tua richiesta e ti forniremo riscontro "
        "sulla base delle informazioni disponibili."
    )


def clean_operator_email_specific_response(text: str) -> str:
    cleaned = strip_markdown(text or "").strip()
    cleaned = re.sub(r"^(?:in merito alla tua richiesta\s*)", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"^(?:oggetto|subject|corpo|body)\s*[:\-]\s*", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.lstrip(" ,;:-")
    cleaned = cleaned.strip()
    if not cleaned:
        return ""
    return cleaned if cleaned.endswith((".", "?", "!")) else f"{cleaned}."


def build_operator_email_body(user_email: str, specific_response: str, operator_name: str) -> str:
    continuation = email_specific_continuation(specific_response, "it")
    return (
        f"Gentile Utente ({user_email}),\n"
        "grazie per averci contattato su T.A.L.O.S., il tuo assistente per i Giochi del Mediterraneo 2026 a Taranto!\n\n"
        f"In merito alla tua richiesta, {continuation}\n\n"
        "Resto a disposizione per eventuali chiarimenti o ulteriori domande!\n\n"
        "A presto,\n"
        f"{operator_name}."
    )


def email_specific_continuation(text: str, language: str) -> str:
    cleaned = str(text or "").strip()
    if normalize_language_code(language, "it") not in {"it", "en", "es", "fr"}:
        return cleaned
    if len(cleaned) > 1 and cleaned[0].isupper() and cleaned[1].islower():
        return f"{cleaned[0].lower()}{cleaned[1:]}"
    return cleaned
