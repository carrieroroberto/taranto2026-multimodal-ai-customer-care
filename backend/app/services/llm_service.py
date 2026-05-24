import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.app.config import settings
from backend.app.services.rag_service import PlannedRetrievalQuery, QueryPlan, RetrievedContext
from backend.app.services import transport_service

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CalendarFact:
    discipline: str | None
    place: str
    schedule: str


VALID_DOMAINS = {
    "calendar",
    "venue",
    "city_sports",
    "ticketing",
    "contacts",
    "volunteering",
    "accessibility",
    "partnership",
    "school_project",
    "history",
    "general",
}

VALID_INTENTS = {
    "event_schedule",
    "venue_information",
    "ticketing",
    "general_information",
    "participation",
}

ENTITY_KEYS = ("discipline", "venue", "city", "date", "item", "transport_stop")

ITALIAN_MARKERS = {
    "ciao", "salve", "buongiorno", "buonasera", "voglio", "vorrei", "posso",
    "puoi", "potresti", "devo", "serve", "aiuto", "dove", "quando", "quanto", "quale",
    "quali", "chi", "che", "cosa", "come", "trovo", "trova", "sono", "sei", "perche", "per",
    "con", "nel", "nella", "degli", "delle", "un", "una", "il", "lo", "la", "tabella", "lingua", "messaggio",
    "risposta", "sempre", "dovrebbe", "selezionata", "risolvi", "problema",
    "biglietti", "operatore", "parlare", "mandato", "inviato", "appena",
    "rispondi", "italiano",
}

ENGLISH_MARKERS = {
    "hello", "hi", "please", "want", "would", "could", "can", "where",
    "when", "what", "which", "who", "how", "why", "is", "are", "ticket", "tickets", "operator",
    "speak", "talk", "help", "english",
}

SPANISH_MARKERS = {
    "hola", "quiero", "quisiera", "puedo", "puedes", "donde", "cuando",
    "que", "quien", "quienes", "cual", "como", "por", "para", "es", "son", "entradas", "operador", "hablar",
    "espanol",
}

FRENCH_MARKERS = {
    "bonjour", "salut", "veux", "voudrais", "peux", "pouvez", "ou",
    "quand", "quoi", "qui", "quel", "quelle", "comment", "pourquoi", "est", "sont", "billets", "operateur",
    "parler", "francais",
}

LANGUAGE_NAMES = {
    "it": "Italiano",
    "en": "English",
    "fr": "Français",
    "es": "Español",
    "ar": "العربية",
}

def detect_message_language(message: str, fallback: str = "it") -> str:
    text = (message or "").strip()
    normalized = normalize_text(text)
    if not normalized:
        return normalize_language_code(fallback)

    if re.search(r"[\u0600-\u06ff]", text):
        return "ar"

    tokens = set(normalized.split())
    scores = {
        "it": language_score(tokens, normalized, ITALIAN_MARKERS),
        "en": language_score(tokens, normalized, ENGLISH_MARKERS),
        "es": language_score(tokens, normalized, SPANISH_MARKERS),
        "fr": language_score(tokens, normalized, FRENCH_MARKERS),
    }
    best_language, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score <= 0:
        return normalize_language_code(fallback)
    return best_language

def language_score(tokens: set[str], normalized: str, markers: set[str]) -> int:
    score = sum(1 for token in tokens if token in markers)
    score += sum(2 for marker in markers if " " in marker and marker in normalized)
    return score


QUERY_PLAN_SYSTEM_PROMPT = """
Sei un analista esperto per i Giochi del Mediterraneo Taranto 2026.
Il tuo compito è analizzare la domanda dell'utente e produrre un piano di ricerca in formato JSON.

Domini validi:
- calendar: date, orari e fasi delle gare (es. "quando ci sono le gare di nuoto?", "programma atletica")
- venue: informazioni sugli impianti e luoghi (es. "dove si gioca a tennis?", "indirizzo stadio")
- city_sports: quali sport si fanno in una città (es. "cosa fanno a Lecce?")
- ticketing: biglietti, costi, dove comprarli
- contacts: come contattare l'organizzazione o i volontari
- volunteering: come diventare volontario
- accessibility: info per disabili
- history: storia dei giochi del mediterraneo
- general: info generali sull'evento

Intenti validi: event_schedule, venue_information, ticketing, general_information, participation.

IMPORTANTE: Rileva la lingua del messaggio dell'utente. Se l'utente scrive in inglese, usa "en", se in spagnolo "es", etc. La "response_language" deve corrispondere alla lingua in cui l'utente sta parlando.

Rispondi SOLO con il JSON, senza spiegazioni.
JSON Schema:
{
  "intent": "...",
  "domains": ["..."],
  "retrieval_queries": [
    {"query": "stringa ottimizzata per ricerca semantica", "domain": "dominio_specifico", "weight": 1.0}
  ],
  "entities": {"discipline": null, "venue": null, "city": null, "date": null},
  "response_language": "it/en/fr/es/ar",
  "needs_clarification": false,
  "clarification_question": null
}
"""

TRANSLATION_SYSTEM_PROMPT = """
Sei un traduttore esperto. Traduci il testo fornito nella lingua richiesta mantenendo il tono istituzionale e cordiale.
Non aggiungere commenti, rispondi solo con la traduzione.
"""

SUMMARY_SYSTEM_PROMPT = """
Sei un assistente esperto nel riassumere conversazioni di assistenza clienti.
Il tuo compito è creare un riassunto sintetico e professionale dell'intera conversazione fornita.
Il riassunto deve essere in LINGUA ITALIANA.
Focus: problema principale dell'utente, eventuali dati forniti e stato della richiesta.
Rispondi solo con il riassunto, senza preamboli o commenti.
"""

def generate_conversation_summary(history: list[dict[str, Any]]) -> str:
    if not history:
        return "Nessuna conversazione disponibile."

    formatted_history = "\n".join(
        f"{'Utente' if h['role'] == 'user' else 'Bot'}: {h['content']}"
        for h in history
    )

    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Conversazione da riassumere:\n\n{formatted_history}"
            },
        ],
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 250,
            "num_ctx": 4096,
        },
    }
    
    try:
        response = call_ollama(payload)
        summary = response.get("message", {}).get("content") or response.get("response")
        if not summary:
            return "Impossibile generare il riassunto."
        return strip_thinking(summary).strip()
    except Exception as exc:
        logger.error("Error generating conversation summary: %s", exc)
        return "Errore durante la generazione del riassunto."

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
    human_keywords = ("umano", "persone", "persona", "esperto", "assistenza", "human", "person", "expert", "support", "real person")
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
        "contacte par un operateur humain"
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
        "fr": "Je n'ai pas d'informations suffisamment précises per vous répondre avec certitude pour le moment. Je peux vous diriger vers le canal officiel ou préparer une demande pour un opérateur.",
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
    history_text = ""
    if history:
        history_text = "Cronologia recente:\n" + "\n".join(
            f"Utente: {h.get('message')}\nBot: {h.get('answer')}"
            for h in history
        ) + "\n\n"

    context_blocks: list[str] = []
    used_chars = 0

    for index, context in enumerate(contexts_for_prompt(contexts, plan), start=1):
        block = format_context_block(index, context)
        if used_chars + len(block) > settings.max_context_chars:
            break
        context_blocks.append(block)
        used_chars += len(block)

    filters = ", ".join(plan.filters) if plan.filters else "nessuno"
    language_name = response_language_name(plan.response_language)
    
    transport_context = transport_service.get_transport_context(plan)
    transport_section = transport_context if transport_context else ""
    
    return (
        f"{history_text}"
        "Domanda utente:\n"
        f"{message}\n\n"
        "Piano JSON sintetico:\n"
        f"{plan_summary_json(plan)}\n\n"
        "Filtri soft principali:\n"
        f"{filters}\n\n"
        "Informazioni disponibili:\n"
        + "\n\n".join(context_blocks)
        + f"{transport_section}"
        + "\n\nIstruzioni di risposta:\n"
        "- usa solo le informazioni disponibili qui sopra;\n"
        "- considera i blocchi in ordine di rilevanza e usa solo quelli che rispondono davvero alla domanda;\n"
        "- se i blocchi non contengono il dato richiesto, rispondi che non hai informazioni sufficienti;\n"
        "- se il dato richiesto e' presente, rispondi solo a quel dato senza aggiungere limitazioni o dati mancanti non richiesti;\n"
        "- se usi un blocco ticketing che indica dati non pubblicati, non dire che l'evento e' gratuito o che non serve biglietto;\n"
        "- se la domanda chiede sia sede sia date, incrocia tutti i record pertinenti e indica sede, citta, date e fasi disponibili;\n"
        "- se la domanda riguarda mobilita, pullman, bus, fermate, parcheggi o come arrivare, usa PRIMA la sezione 'INFORMAZIONI TRASPORTI (SQL DB)' se presente, altrimenti usa i dati del blocco della sede;\n"
        "- collega sempre le informazioni di trasporto ai Giochi del Mediterraneo Taranto 2026, spiegando come raggiungere le sedi di gara o i punti di interesse dell'evento;\n"
        "- per le domande sulle linee bus e orari fai ESCLUSIVO affidamento alla sezione 'INFORMAZIONI TRASPORTI (SQL DB)', elencando fermate, linee e orari esatti trovati (che sono sincronizzati con l'orario attuale);\n"
        "- se mancano informazioni essenziali per rispondere (es. punto di partenza per un percorso), chiedi gentilmente all'utente di specificarle nel contesto della sua visita ai Giochi;\n"
        "- non omettere nessuna data o fase riportata nelle righe 'Date e fasi';\n"
        "- se ci sono piu sedi per la stessa disciplina, sintetizzale senza scegliere solo la prima;\n"
        f"- rispondi in {language_name}, la stessa lingua della domanda originale;\n"
        "- non scrivere URL nel testo e non aggiungere formule finali generiche;\n"
        "- rispondi in massimo 4 frasi brevi."
    )


def plan_summary_json(plan: QueryPlan) -> str:
    return json.dumps(
        {
            "language": plan.response_language,
            "intent": plan.intent,
            "domains": plan.domains,
            "normalized_query": plan.retrieval_query,
            "entities": plan.entities,
            "retrieval_queries": [
                {
                    "query": query.query,
                    "domain": query.domain,
                    "weight": query.weight,
                }
                for query in plan.retrieval_queries
            ],
            "needs_clarification": plan.needs_clarification,
            "clarification_question": plan.clarification_question,
        },
        ensure_ascii=False,
    )


def contexts_for_prompt(
    contexts: list[RetrievedContext],
    plan: QueryPlan,
) -> list[RetrievedContext]:
    if plan.domain == "calendar":
        preferred = [
            context
            for context in contexts
            if context_type(context) in {"event_schedule", "event_schedule_overview"}
        ]
        if preferred:
            return preferred
    return contexts


def format_context_block(index: int, context: RetrievedContext) -> str:
    lines = [
        f"[{index}] {context.title or 'Fonte recuperata'}",
        f"Tipo: {context.item_type or 'non disponibile'}",
    ]
    if context.address:
        lines.append(f"Indirizzo: {context.address}")
    schedule_summary = extract_schedule_summary(context.document)
    if schedule_summary:
        lines.append(f"Date e fasi: {schedule_summary}")
    lines.append(f"Contenuto: {compact_document(context.document)}")
    return "\n".join(lines)


def extract_schedule_summary(document: str) -> str | None:
    patterns = (
        r"Le giornate e le fasi riportate sono:\s*([^\.]+)",
        r"Il calendario associato alla sede riporta queste date e fasi:\s*([^\.]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, document, flags=re.IGNORECASE)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()
    return None


def ensure_calendar_completeness(
    answer: str,
    message: str,
    plan: QueryPlan,
    contexts: list[RetrievedContext],
) -> str:
    if not should_enforce_calendar_completeness(message, plan):
        return answer

    facts = calendar_facts(contexts)
    if len(facts) < 2:
        return answer

    normalized_answer = normalize_text(answer)
    missing_fact = any(
        not fact_is_covered(fact, normalized_answer) for fact in facts
    )
    if missing_fact:
        return calendar_summary_answer(facts)
    return answer


def should_enforce_calendar_completeness(message: str, plan: QueryPlan) -> bool:
    return plan.domain == "calendar" or "calendar" in plan.domains or plan.intent == "event_schedule"


def calendar_facts(contexts: list[RetrievedContext]) -> list[CalendarFact]:
    facts: list[CalendarFact] = []
    seen: set[tuple[str | None, str, str]] = set()

    for context in contexts:
        if context_type(context) != "event_schedule":
            continue
        schedule = extract_schedule_summary(context.document)
        if not schedule:
            continue
        discipline, place = split_calendar_title(context.title)
        key = (discipline, place, schedule)
        if key in seen:
            continue
        facts.append(CalendarFact(discipline=discipline, place=place, schedule=schedule))
        seen.add(key)
    return facts


def split_calendar_title(title: str | None) -> tuple[str | None, str]:
    if title and " - " in title:
        discipline, place = title.split(" - ", 1)
        return discipline.strip(), place.strip()
    return None, (title or "sede indicata").strip()


def fact_is_covered(fact: CalendarFact, normalized_answer: str) -> bool:
    place_terms = [
        term
        for term in normalize_text(fact.place).split()
        if len(term) > 3
    ]
    days = re.findall(r"\b\d{1,2}\b", fact.schedule)
    place_covered = not place_terms or any(term in normalized_answer for term in place_terms)
    dates_covered = all(day in normalized_answer for day in days)
    return place_covered and dates_covered


def calendar_summary_answer(facts: list[CalendarFact]) -> str:
    discipline = facts[0].discipline or "questa disciplina"
    items = "; ".join(f"{fact.place} ({fact.schedule})" for fact in facts)
    return f"Le gare di {discipline} sono previste in queste sedi: {items}."


def enforce_ticketing_guardrail(
    answer: str,
    plan: QueryPlan,
    contexts: list[RetrievedContext],
) -> str:
    if not asks_ticketing_info(plan) or not has_ticketing_context(contexts):
        return answer

    sentences = split_sentences(answer)
    cleaned_sentences = [
        sentence
        for sentence in sentences
        if not has_unsafe_ticketing_claim(sentence)
    ]
    if len(cleaned_sentences) == len(sentences):
        return answer

    cleaned = " ".join(cleaned_sentences).strip()
    notice = ticketing_status_notice(plan.response_language)
    if not cleaned:
        return notice
    return f"{cleaned} {notice}"


def asks_ticketing_info(plan: QueryPlan) -> bool:
    return (
        plan.domain == "ticketing"
        or "ticketing" in plan.domains
        or plan.intent == "ticketing"
        or any(query.domain == "ticketing" for query in plan.retrieval_queries)
    )


def has_ticketing_context(contexts: list[RetrievedContext]) -> bool:
    return any(context_type(context) == "ticketing" for context in contexts)


def split_sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]


def has_unsafe_ticketing_claim(sentence: str) -> bool:
    normalized = normalize_text(sentence)
    unsafe_patterns = (
        "non e necessario acquistare biglietti",
        "non e necessario il biglietto",
        "non serve biglietto",
        "non serve il biglietto",
        "non richiede biglietto",
        "non richiede un biglietto",
        "ingresso gratuito",
        "evento gratuito",
        "gratis",
        "no ticket is required",
        "ticket is not required",
        "does not require a ticket",
        "no need to buy tickets",
        "not necessary to buy tickets",
        "free event",
    )
    return contains_any(normalized, unsafe_patterns)


def ticketing_status_notice(response_language: str) -> str:
    language = normalize_language_code(response_language)
    notices = {
        "it": (
            "Per i biglietti, al momento non sono pubblicati prezzi, canali di "
            "acquisto, disponibilita o distinzione tra eventi gratuiti e a pagamento."
        ),
        "en": (
            "For tickets, confirmed prices, purchase channels, availability and "
            "free/paid status are not available yet."
        ),
        "fr": (
            "Pour les billets, les prix, les canaux d'achat, la disponibilite et "
            "le statut gratuit/payant ne sono pas ancora publies."
        ),
        "es": (
            "Para las entradas, todavia no estan publicados prezzi, canales de "
            "compra, disponibilidad ni estado gratuito/de pago."
        ),
    }
    return notices.get(language, notices["it"])


def compact_document(document: str) -> str:
    compacted = re.sub(r"\s+", " ", document).strip()
    max_chars = max(260, settings.max_context_chars // max(settings.n_results, 1))
    if len(compacted) <= max_chars:
        return compacted
    return compacted[: max_chars - 3].rstrip() + "..."


def translate_static_answer(answer: str, response_language: str) -> str:
    lang_code = normalize_language_code(response_language)
    if lang_code == "it":
        return answer
    try:
        # Force translation for static strings
        return translate_text(answer, lang_code)
    except Exception as exc:
        logger.warning(
            "static_answer_translation_fallback language=%s error=%s",
            lang_code,
            exc,
        )
        return answer


def clean_answer_text(answer: str) -> str:
    answer = re.sub(r"(^|\n)\s*fonti\s*:.*$", "", answer, flags=re.IGNORECASE | re.DOTALL)
    answer = re.sub(r"https?://\S+", "la pagina ufficiale", answer)
    answer = re.sub(
        r"\b(la\s+)?sede\s+indicata\s+dalla\s+(base informativa|base dati)\s+(e|e')\b",
        "La sede e",
        answer,
        flags=re.IGNORECASE,
    )
    answer = re.sub(
        r"\b(secondo|in base a)\s+(la\s+)?(base informativa|base dati|contesto fornito|contesto)\s*,?\s*",
        "",
        answer,
        flags=re.IGNORECASE,
    )
    answer = re.sub(
        r"\b(la\s+)?(base informativa|base dati|contesto fornito|contesto)\b",
        "il programma",
        answer,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+\n", "\n", answer).strip()


def context_type(context: RetrievedContext) -> str:
    return normalize_text(context.item_type).replace(" ", "_")


def translate_text(text: str, target_language: str) -> str:
    # Always attempt translation unless we are absolutely sure target == source
    # Since we don't know the source, we let the LLM decide or try to translate.
    # To avoid infinite loops or useless work, we only skip if text is empty.
    if not text.strip():
        return text

    target_lang_name = response_language_name(target_language)
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": TRANSLATION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Lingua richiesta: {target_lang_name}\n\n"
                    f"Testo da tradurre:\n{text}"
                ),
            },
        ],
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0,
            "num_predict": min(settings.llm_num_predict, 180),
            "num_ctx": 1024,
        },
    }
    response = call_ollama(payload)
    translated = response.get("message", {}).get("content") or response.get("response")
    if not translated:
        from backend.app.services.errors import DependencyServiceError
        raise DependencyServiceError("Ollama returned an empty translation.")
    return strip_thinking(translated).strip()


def call_ollama(
    payload: dict[str, Any],
    timeout: int | None = None,
) -> dict[str, Any]:
    url = settings.ollama_base_url.rstrip("/") + "/api/chat"
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout or settings.llm_timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        from backend.app.services.errors import DependencyServiceError
        raise DependencyServiceError(
            f"Ollama error for model {settings.ollama_model}: HTTP {exc.code} {detail}"
        ) from exc
    except (TimeoutError, URLError) as exc:
        from backend.app.services.errors import DependencyServiceError
        raise DependencyServiceError(
            f"Ollama unavailable at {settings.ollama_base_url}: {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        from backend.app.services.errors import DependencyServiceError
        raise DependencyServiceError(f"Ollama returned invalid JSON: {exc}") from exc


def parse_json_object(value: str | None) -> dict[str, Any]:
    if not value:
        raise ValueError("Cannot parse empty JSON.")
    cleaned = strip_thinking(value).strip()
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        raise ValueError("Parser did not return JSON.")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Parser JSON is not an object.")
    return parsed


def strip_thinking(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"<think>.*?</think>", "", value, flags=re.DOTALL | re.IGNORECASE)


def string_list(value: Any, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in items:
            items.append(text)
        if len(items) == limit:
            break
    return items


def merge_queries(*groups: list[str]) -> list[str]:
    queries: list[str] = []
    for group in groups:
        queries.extend(group)
    return deduplicate_queries(queries)


def deduplicate_queries(queries: list[str]) -> list[str]:
    deduplicated: list[str] = []
    seen: set[str] = set()
    for item in queries:
        normalized = normalize_text(item)
        if normalized and normalized not in seen:
            deduplicated.append(item)
            seen.add(normalized)
    return deduplicated


def parse_retrieval_queries(
    value: Any,
    fallback_query: str,
    fallback_domains: list[str],
) -> list[PlannedRetrievalQuery]:
    queries: list[PlannedRetrievalQuery] = []
    if isinstance(value, list):
        for item in value[:4]:
            if not isinstance(item, dict):
                continue
            query = str(item.get("query") or "").strip()
            if not query:
                continue
            queries.append(
                PlannedRetrievalQuery(
                    query=query,
                    domain=optional_domain(item.get("domain")),
                    weight=normalized_weight(item.get("weight")),
                )
            )

    if not queries:
        domain = None if fallback_domains == ["general"] else fallback_domains[0]
        queries.append(PlannedRetrievalQuery(query=fallback_query, domain=domain, weight=1.0))

    return deduplicate_planned_queries(queries)


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


def normalized_weight(value: Any) -> float:
    try:
        weight = float(value)
    except (TypeError, ValueError):
        return 1.0
    return min(max(weight, 0.1), 2.0)


def normalize_domains(value: Any, fallback: Any = None) -> list[str]:
    raw_domains = value if isinstance(value, list) else [fallback]
    domains: list[str] = []
    for item in raw_domains:
        domain = normalize_domain(item)
        if domain and domain not in domains:
            domains.append(domain)
    return domains or ["general"]


def normalize_domain(value: Any) -> str | None:
    if value is None:
        return None
    normalized = normalize_text(value).replace(" ", "_")
    if normalized in {"none", "null", ""}:
        return None
    return normalized if normalized in VALID_DOMAINS else "general"


def optional_domain(value: Any) -> str | None:
    domain = normalize_domain(value)
    return None if domain == "general" else domain


def primary_domain(domains: list[str]) -> str:
    for domain in domains:
        if domain != "general":
            return domain
    return "general"


def normalize_intent(value: Any) -> str:
    intent = normalize_text(value).replace(" ", "_")
    return intent if intent in VALID_INTENTS else "unknown"


def normalized_entities(value: Any) -> dict[str, str | None]:
    entities: dict[str, str | None] = {}
    raw = value if isinstance(value, dict) else {}
    for key in ENTITY_KEYS:
        entities[key] = optional_string(raw.get(key))
    return entities


def optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = text.replace("\u2019", "'").replace("`", "'")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def contains_any(haystack: str, terms: tuple[str, ...]) -> bool:
    return any(term in haystack for term in terms)


def normalize_language_code(value: Any) -> str:
    language = str(value or "it").strip().lower()
    if language in {"italian", "italiano"}:
        return "it"
    if language in {"english", "inglese"}:
        return "en"
    if language in {"french", "francese"}:
        return "fr"
    if language in {"spanish", "spagnolo", "espanol"}:
        return "es"
    if language in {"german", "tedesco"}:
        return "de"
    if re.fullmatch(r"[a-z]{2,3}", language):
        return language
    return "it"


def response_language_name(language: str) -> str:
    language = normalize_language_code(language)
    return LANGUAGE_NAMES.get(language, language)
