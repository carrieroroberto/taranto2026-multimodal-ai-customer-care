import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.app.config import settings
from backend.app.services.errors import DependencyServiceError
from backend.app.services.rag_service import (
    CalendarFact,
    PlannedRetrievalQuery,
    QueryPlan,
    RetrievedContext,
)


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """Sei un agent AI multimodale per il customer care cittadino durante i Giochi del Mediterraneo 2026 a Taranto.
Ora rispondi a richieste testuali via API con tono chiaro, ufficiale e utile per cittadini, turisti, spettatori e operatori.
Usa solo le informazioni fornite nel prompt utente.
Controlla sempre l'elenco completo delle sedi e delle cittÃ  (Brindisi, Lecce, ecc.) prima di dichiarare che una localitÃ  non Ã¨ coinvolta.
Rispondi nella stessa lingua della domanda originale, indicata nel prompt come lingua di risposta.
Non inventare sport (es. pesca), prezzi, disponibilita, canali di acquisto, orari esatti, risultati live, atleti, coordinate o link Maps.
Se il contesto ticketing dice che i biglietti non sono ancora disponibili o pubblicati, non dire mai che l'evento e' gratuito o che non serve biglietto.
Se le informazioni fornite non contengono la risposta, dillo chiaramente e non usare conoscenza generale.
Se un dato manca, dillo e proponi verifica ufficiale o operatore.
Scrivi come un operatore umano: non citare base informativa, contesto, record, retrieval o fonti recuperate.
Se la domanda richiede piu sedi, date o fasi, sintetizza tutti i dati pertinenti recuperati e non fermarti al primo risultato.
Se la domanda riguarda un'edizione storica dei Giochi del Mediterraneo, non ricondurla a Taranto 2026.
Rispondi in massimo 4 frasi brevi, senza formule finali generiche.
Non usare "probabilmente": se il contesto conferma un dato, affermalo; se non lo conferma, dichiara che manca.
Usa la denominazione esatta presente nel contesto per sport, sedi, citta e persone, anche se la domanda contiene refusi.
Non scrivere URL nel testo: il backend li aggiunge come fonti strutturate.
Non citare dettagli tecnici interni. Non usare tag <think>."""


PARSER_SYSTEM_PROMPT = """Sei il query planner del chatbot Taranto 2026.
Usa la cronologia della conversazione per risolvere riferimenti anaforici (es. "lui", "quello", "lì") e capire il contesto.
Restituisci solo JSON valido e compatto su una sola riga, senza markdown e senza risposta finale.
Schema:
{
  "query_it": "...",
  "language": "it|en|fr|es|de|other",
  "intent": "general_info|event_schedule|venue_info|ticketing|transport|accessibility|volunteering|history|contacts|complaint|unknown",
  "domains": ["general", "calendar"],
  "normalized_query": "...",
  "entities": {
    "sport": null,
    "city": null,
    "venue": null,
    "date": null,
    "event": null,
    "ticket_type": null
  },
  "filters": ["..."],
  "expanded_queries": ["..."],
  "retrieval_queries": [
    {"query": "...", "domain": "calendar", "weight": 1.0}
  ],
  "needs_clarification": false,
  "clarification_question": null
}
Regole:
- query_it e normalized_query devono essere in italiano per il retrieval;
- correggi refusi evidenti e traduci semanticamente query non italiane;
- scomponi richieste multi-dominio in massimo 4 retrieval_queries;
- domains e domain sono solo hint per il retrieval;
- filters contiene solo entita/concetti specifici, non parole generiche;
- usa null per entita assenti;
- non inventare fatti, date, prezzi, sedi, link o risultati."""


TRANSLATION_SYSTEM_PROMPT = """Traduci il testo nella lingua richiesta.
Mantieni significato, tono customer-care e dati fattuali.
Non aggiungere informazioni, URL o spiegazioni."""


@dataclass(frozen=True)
class QueryAnalysis:
    query_it: str
    language: str
    intent: str
    domains: list[str]
    normalized_query: str
    entities: dict[str, str | None]
    filters: list[str]
    expanded_queries: list[str]
    retrieval_queries: list[PlannedRetrievalQuery]
    needs_clarification: bool
    clarification_question: str | None


LANGUAGE_NAMES = {
    "it": "italiano",
    "en": "inglese",
    "fr": "francese",
    "es": "spagnolo",
    "de": "tedesco",
}

VALID_DOMAINS = {
    "general",
    "ticketing",
    "venue",
    "calendar",
    "volunteering",
    "history",
    "contacts",
    "accessibility",
    "motto",
    "partnership",
    "school_project",
    "city_sports",
}

VALID_INTENTS = {
    "general_info",
    "event_schedule",
    "venue_info",
    "ticketing",
    "transport",
    "accessibility",
    "volunteering",
    "history",
    "contacts",
    "complaint",
    "unknown",
}

ENTITY_KEYS = ("sport", "city", "venue", "date", "event", "ticket_type")


def analyze_query(query: str, history: list[dict[str, Any]] | None = None) -> QueryAnalysis:
    history_text = ""
    if history:
        history_text = "Cronologia recente:\n" + "\n".join(
            f"Utente: {h.get('message')}\nBot: {h.get('answer')}"
            for h in history
        ) + "\n\n"

    payload = {
        "model": settings.query_parser_model,
        "messages": [
            {"role": "system", "content": PARSER_SYSTEM_PROMPT},
            {"role": "user", "content": f"{history_text}Domanda attuale: {query}"},
        ],
        "format": "json",
        "stream": False,
        "think": False,
        "keep_alive": "30m",
        "options": {
            "temperature": 0,
            "num_predict": max(settings.query_parser_num_predict, 420),
            "num_ctx": 1024,
        },
    }
    response = call_ollama(
        payload,
        timeout=max(
            settings.query_parser_timeout_seconds,
            settings.llm_timeout_seconds,
            150,
        ),
    )
    content = response.get("message", {}).get("content", "")
    parsed = parse_json_object(content)

    query_it = str(
        parsed.get("query_it")
        or parsed.get("normalized_query")
        or query
    ).strip()
    normalized_query = str(parsed.get("normalized_query") or query_it).strip()
    domains = normalize_domains(parsed.get("domains"), parsed.get("domain"))
    retrieval_queries = parse_retrieval_queries(
        parsed.get("retrieval_queries"),
        fallback_query=normalized_query or query_it or query,
        fallback_domains=domains,
    )

    return QueryAnalysis(
        query_it=query_it,
        language=normalize_language_code(parsed.get("language")),
        intent=normalize_intent(parsed.get("intent")),
        domains=domains,
        normalized_query=normalized_query,
        entities=normalized_entities(parsed.get("entities")),
        filters=string_list(parsed.get("filters"), limit=8),
        expanded_queries=string_list(parsed.get("expanded_queries"), limit=4),
        retrieval_queries=retrieval_queries,
        needs_clarification=bool(parsed.get("needs_clarification", False)),
        clarification_question=optional_string(parsed.get("clarification_question")),
    )


def build_query_plan(query: str, history: list[dict[str, Any]] | None = None) -> QueryPlan:
    try:
        return build_llm_query_plan(query, history)
    except Exception as exc:
        logger.warning("query_parser_fallback error=%s", exc)
        return fallback_query_plan(query)


def build_llm_query_plan(query: str, history: list[dict[str, Any]] | None = None) -> QueryPlan:
    analysis = analyze_query(query, history)
    retrieval_query = analysis.normalized_query or analysis.query_it or query
    expanded_queries = deduplicate_queries(
        [
            retrieval_query,
            *analysis.expanded_queries,
            *[item.query for item in analysis.retrieval_queries],
        ]
    )[:4]
    domains = analysis.domains or ["general"]
    domain = primary_domain(domains)

    return QueryPlan(
        original_query=query,
        retrieval_query=retrieval_query,
        response_language=analysis.language,
        domain=domain,
        filters=analysis.filters,
        expanded_queries=expanded_queries,
        intent=analysis.intent,
        domains=domains,
        entities=analysis.entities,
        retrieval_queries=analysis.retrieval_queries,
        needs_clarification=analysis.needs_clarification,
        clarification_question=analysis.clarification_question,
    )


def fallback_query_plan(query: str) -> QueryPlan:
    retrieval_query = query.strip()
    return QueryPlan(
        original_query=query,
        retrieval_query=retrieval_query,
        response_language="it",
        domain="general",
        filters=[],
        expanded_queries=[retrieval_query],
        intent="unknown",
        domains=["general"],
        entities={},
        retrieval_queries=[
            PlannedRetrievalQuery(query=retrieval_query, domain=None, weight=1.0)
        ],
        needs_clarification=False,
        clarification_question=None,
    )


def generate_grounded_answer(prompt: str, response_language: str) -> str:
    language_name = response_language_name(response_language)
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
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
    if not contexts:
        answer = unavailable_answer(plan.response_language)
    elif should_escalate and reason in {
        "human_operator_requested",
        "urgent_request",
        "live_data_unavailable",
        "complaint_or_lost_item",
    }:
        answer = unavailable_answer(plan.response_language)
    elif plan.domain == "ticketing" and set(plan.domains).issubset({"ticketing", "general"}):
        answer = ticketing_guardrail_answer(plan.response_language)
    else:
        prompt = build_user_prompt(message, plan, contexts, history)
        answer = generate_grounded_answer(prompt, plan.response_language)
        answer = ensure_calendar_completeness(answer, message, plan, contexts)
        answer = enforce_ticketing_guardrail(answer, plan, contexts)

    return clean_answer_text(answer)


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
        + "\n\nIstruzioni di risposta:\n"
        "- usa solo le informazioni disponibili qui sopra;\n"
        "- considera i blocchi in ordine di rilevanza e usa solo quelli che rispondono davvero alla domanda;\n"
        "- se i blocchi non contengono il dato richiesto, rispondi che non hai informazioni sufficienti;\n"
        "- se il dato richiesto e' presente, rispondi solo a quel dato senza aggiungere limitazioni o dati mancanti non richiesti;\n"
        "- se usi un blocco ticketing che indica dati non pubblicati, non dire che l'evento e' gratuito o che non serve biglietto;\n"
        "- se la domanda chiede sia sede sia date, incrocia tutti i record pertinenti e indica sede, citta, date e fasi disponibili;\n"
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
            "le statut gratuit/payant ne sont pas encore publies."
        ),
        "es": (
            "Para las entradas, todavia no estan publicados precios, canales de "
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


def unavailable_answer(response_language: str = "it") -> str:
    answer = (
        "Al momento non ho un dato abbastanza preciso per risponderti con sicurezza. "
        "Posso indicarti il canale ufficiale o preparare una richiesta per un operatore."
    )
    return translate_static_answer(answer, response_language)


def ticketing_guardrail_answer(response_language: str = "it") -> str:
    answer = (
        "Al momento i biglietti per Taranto 2026 non risultano ancora disponibili. "
        "Non sono ancora pubblicati ufficialmente prezzi, canali di acquisto, "
        "disponibilita o distinzione tra eventi gratuiti e a pagamento."
    )
    return translate_static_answer(answer, response_language)


def translate_static_answer(answer: str, response_language: str) -> str:
    if response_language == "it":
        return answer
    try:
        return translate_text(answer, response_language)
    except DependencyServiceError as exc:
        logger.warning(
            "static_answer_translation_fallback language=%s error=%s",
            response_language,
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
    if normalize_language_code(target_language) == "it":
        return text

    language_name = response_language_name(target_language)
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": TRANSLATION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Lingua richiesta: {language_name}\n\n"
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
        raise DependencyServiceError(
            f"Ollama error for model {settings.ollama_model}: HTTP {exc.code} {detail}"
        ) from exc
    except (TimeoutError, URLError) as exc:
        raise DependencyServiceError(
            f"Ollama unavailable at {settings.ollama_base_url}: {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise DependencyServiceError(f"Ollama returned invalid JSON: {exc}") from exc


def parse_json_object(value: str) -> dict[str, Any]:
    cleaned = strip_thinking(value).strip()
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        raise ValueError("Parser did not return JSON.")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Parser JSON is not an object.")
    return parsed


def strip_thinking(value: str) -> str:
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
