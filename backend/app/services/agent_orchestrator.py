import logging
import re
import unicodedata
from typing import Annotated, Any, Dict, List, Optional, TypedDict
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, END
from backend.app.services.llm_service import (
    build_query_plan,
    build_answer,
    explicit_operator_requested,
    human_operator_answer,
    unavailable_answer,
    is_refusal_answer,
    answer_repeats_user_text,
    normalize_text,
    translate_text,
)
from backend.app.services.rag_service import (
    retrieve_context,
    select_answer_candidates,
    to_context,
    QueryPlan,
    RetrievedContext
)
from backend.app.schemas.chat import ChatRequestDTO, SourceDTO, TicketDraftDTO

logger = logging.getLogger(__name__)

class AgentState(TypedDict):
    # Input
    message: str
    history: List[Dict[str, Any]]
    language: str
    visual_context: Optional[str]
    
    # Internal state
    plan: Optional[QueryPlan]
    contexts: List[RetrievedContext]
    answer: str
    should_escalate: bool
    escalation_reason: Optional[str]
    sources: List[SourceDTO]
    maps: Optional[str]

def robust_normalize(text: str) -> str:
    if not text: return ""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()

SOURCE_STOP_TERMS = {
    "2026", "ai", "al", "alla", "allo", "anche", "assistenza", "assistente",
    "bot", "chat", "ciao", "come", "con", "dato", "dei", "del", "della",
    "delle", "di", "domanda", "essere", "giochi", "gli", "help", "il", "in",
    "informazione", "informazioni", "io", "la", "le", "mediterraneo",
    "mediterranei", "momento", "non", "oggi", "per", "posso", "preciso",
    "questa", "questo", "risponderti", "sicurezza", "sono", "su", "talos",
    "taranto", "ti", "tuo", "ufficiale", "un", "una",
}

SERVICE_ANSWER_PATTERNS = (
    "ciao sono talos",
    "come posso aiutarti",
    "come posso aiutarla",
    "how can i help",
    "how may i help",
    "como puedo ayudarte",
    "comment puis je vous aider",
    "scrivi la tua email",
    "inserisci la tua email",
    "write your email",
    "enter your email",
    "verrai ricontattato",
    "human operator",
    "operatore umano",
    "al momento non ho un dato abbastanza preciso",
    "i don t have enough precise information",
    "i don't have enough precise information",
    "no tengo informacion suficientemente precisa",
    "je n ai pas d informations suffisamment precises",
)

async def planning_node(state: AgentState) -> Dict[str, Any]:
    logger.info("Node: planning")
    message = state["message"]
    history = state["history"]
    visual_context = state.get("visual_context")
    
    plan = await build_query_plan(message, history, state["language"])

    if explicit_operator_requested(message):
        return {
            "plan": plan,
            "should_escalate": False,
            "escalation_reason": "human_operator_requested",
            "answer": human_operator_answer(plan.response_language)
        }
    
    if visual_context:
        from backend.app.services.rag_service import PlannedRetrievalQuery
        import dataclasses
        visual_context_it = await translate_text(visual_context, "it")
        anchored_query = f"{visual_context_it} Giochi del Mediterraneo Taranto 2026"
        new_queries = list(plan.retrieval_queries)
        new_queries.append(PlannedRetrievalQuery(query=anchored_query, domain="general", weight=1.5))
        new_queries.append(PlannedRetrievalQuery(query=visual_context_it, domain="general", weight=1.0))
        new_expanded = list(plan.expanded_queries)
        new_expanded.extend([visual_context_it, anchored_query])
        plan = dataclasses.replace(plan, retrieval_queries=new_queries, expanded_queries=new_expanded)

    return {"plan": plan}

async def retrieval_node(state: AgentState) -> Dict[str, Any]:
    logger.info("Node: retrieval")
    if state.get("answer"):
        return {}
    plan = state.get("plan")
    if not plan:
        return {}
    candidates = retrieve_context(plan, n_results=8)
    answer_candidates = select_answer_candidates(candidates, plan)
    contexts = [to_context(candidate) for candidate in answer_candidates]
    return {"contexts": contexts}

async def generation_node(state: AgentState) -> Dict[str, Any]:
    logger.info("Node: generation")
    plan = state.get("plan")
    contexts = state.get("contexts", [])
    message = state["message"]
    if state.get("answer"):
        return {}

    should_escalate = False
    reason = None
    if not contexts:
        response_language = plan.response_language if plan else state["language"]
        return {
            "answer": unavailable_answer(response_language),
            "should_escalate": False,
            "escalation_reason": "no_context"
        }
    
    answer = await build_answer(
        message,
        plan,
        contexts,
        False,
        None,
        state["history"],
        state.get("visual_context"),
    )
    if is_refusal_answer(answer) or answer_repeats_user_text(answer, message):
        should_escalate = False
        reason = "immediate_refusal"
        answer = unavailable_answer(plan.response_language)
        
    return {
        "answer": answer,
        "should_escalate": should_escalate,
        "escalation_reason": reason
    }

async def postprocessing_node(state: AgentState) -> Dict[str, Any]:
    logger.info("Node: postprocessing")
    answer = state.get("answer", "")
    contexts = state.get("contexts", [])
    plan = state.get("plan")
    
    if not answer:
        return {"sources": [], "maps": None}

    if should_suppress_sources(answer):
        return {"sources": [], "maps": None}

    norm_ans = robust_normalize(answer)
    source_contexts = contexts_supporting_answer(answer, contexts, plan)
    initial_sources = []
    seen_urls = set()
    for ctx in source_contexts:
        if ctx.source_url and ctx.source_url not in seen_urls:
            initial_sources.append(SourceDTO(
                title=ctx.title or ctx.item_id, 
                url=ctx.source_url, 
                type=ctx.item_type,
                maps_url=ctx.maps_url
            ))
            seen_urls.add(ctx.source_url)
    
    # VENUE DETECTION LOGIC
    # We only count a context as a "Venue" if its type suggests a physical location
    VENUE_TYPES = {"venue", "venue_geocoding", "schedule", "transport"}
    VENUE_KEYWORDS = {
        "stadio", "palazzetto", "pala", "hall", "centro sportivo", "impianto", "piscina", 
        "campo", "park", "parco", "center", "stadium", "circolo", "porto", "nautic", "torre",
        "arena", "villa", "piazza", "teatro", "museo"
    }
    
    mentioned_maps = []
    
    for c in source_contexts:
        if not c.maps_url:
            continue
        
        # Determine if this context is actually a physical structure
        is_real_venue = (c.item_type in VENUE_TYPES) or any(k in robust_normalize(c.title or "") for k in VENUE_KEYWORDS)
        if not is_real_venue:
            continue

        # Extract specific structure name from title
        title = c.title or ""
        parts = re.split(r'[-–,]', title)
        structure_name = robust_normalize(parts[0])
        
        # Blacklist generic terms that shouldn't trigger Maps on their own
        STOP_WORDS = {"taranto", "puglia", "italia", "comune", "comitato", "giochi", "mediterraneo", "mascotte", "ionios"}
        if structure_name in STOP_WORDS or len(structure_name) <= 3:
            continue

        is_mentioned = False
        if structure_name in norm_ans:
            is_mentioned = True
        elif c.address and robust_normalize(c.address) in norm_ans:
            is_mentioned = True
            
        if is_mentioned:
            if c.maps_url not in mentioned_maps:
                mentioned_maps.append(c.maps_url)
    
    final_answer = answer
    maps = None
    sources = initial_sources
    
    # 1 Venue = Icon
    if len(mentioned_maps) == 1:
        maps = mentioned_maps[0]
        icon_shown = False
        for s in sources:
            if s.maps_url == maps and not icon_shown:
                icon_shown = True
            else:
                s.maps_url = None
        
        map_source = next((s for s in sources if s.maps_url == maps), None)
        if not map_source:
            map_source = SourceDTO(title="Vedi su Google Maps", url=maps, type="map", maps_url=maps)
            sources.insert(0, map_source)
        else:
            sources.remove(map_source)
            sources.insert(0, map_source)

    # >1 Venues = Clarification Suffix
    elif len(mentioned_maps) > 1:
        for s in sources:
            s.maps_url = None
        maps = None
        suffix = " Vuoi sapere la posizione di un posto specifico tra questi?"
        if suffix not in answer:
            final_answer = f"{answer.rstrip()} {suffix}".strip()
    
    # Mascot or No Venue = No Icons
    else:
        for s in sources:
            s.maps_url = None
        maps = None

    return {
        "answer": final_answer,
        "sources": sources[:3],
        "maps": maps
    }


def should_suppress_sources(answer: str) -> bool:
    normalized = robust_normalize(answer)
    if not normalized:
        return True

    if any(pattern in normalized for pattern in SERVICE_ANSWER_PATTERNS):
        return True

    tokens = normalized.split()
    meaningful = [token for token in tokens if token not in SOURCE_STOP_TERMS and len(token) >= 4]
    if len(tokens) <= 16 and len(meaningful) <= 2 and any(token in {"ciao", "salve", "hello", "hola", "bonjour"} for token in tokens):
        return True

    return False


def contexts_supporting_answer(
    answer: str,
    contexts: List[RetrievedContext],
    plan: Optional[QueryPlan],
) -> List[RetrievedContext]:
    terms = source_match_terms(answer)
    if not terms:
        return []

    normalized_answer = robust_normalize(answer)
    answer_numbers = set(re.findall(r"\b\d{1,4}\b", answer))
    supported: List[RetrievedContext] = []

    for ctx in contexts:
        if not ctx.source_url:
            continue
        if source_type_inappropriate(ctx, normalized_answer, plan):
            continue

        context_text = robust_normalize(
            " ".join(
                str(part or "")
                for part in [ctx.item_id, ctx.title, ctx.item_type, ctx.address, ctx.document]
            )
        )
        if not context_text:
            continue

        term_hits = sum(1 for term in terms if term in context_text)
        number_hit = bool(answer_numbers and any(number in context_text for number in answer_numbers))
        title_hit = bool(ctx.title and robust_normalize(ctx.title) in normalized_answer)

        support_score = term_hits + (2 if number_hit else 0) + (2 if title_hit else 0)
        if support_score >= 2:
            supported.append(ctx)

    return supported


def source_match_terms(answer: str) -> set[str]:
    normalized = robust_normalize(answer)
    terms: set[str] = set()
    for token in normalized.split():
        if token in SOURCE_STOP_TERMS:
            continue
        if len(token) < 4:
            continue
        terms.add(token)
    return terms


def source_type_inappropriate(
    ctx: RetrievedContext,
    normalized_answer: str,
    plan: Optional[QueryPlan],
) -> bool:
    item_type = robust_normalize(ctx.item_type or "")
    title = robust_normalize(ctx.title or "")
    query_text = robust_normalize(getattr(plan, "original_query", "") if plan else "")
    combined_request = f"{query_text} {normalized_answer}"

    if "contact" in item_type or "contatt" in item_type or "contact" in title or "contatt" in title:
        return not any(
            term in combined_request
            for term in ("contatto", "contatti", "email", "telefono", "segreteria", "supporto", "operatore", "contact", "phone")
        )

    if "historical_results_page" in item_type or "risultati storici" in item_type:
        return not any(
            term in combined_request
            for term in ("storia", "storico", "storici", "risultati", "medaglie", "medagliere", "edizione", "pescara", "oran", "mersin", "athens", "casablanca")
        )

    return False

def create_orchestrator():
    workflow = StateGraph(AgentState)
    workflow.add_node("planner", planning_node)
    workflow.add_node("retriever", retrieval_node)
    workflow.add_node("generator", generation_node)
    workflow.add_node("postprocess", postprocessing_node)
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "retriever")
    workflow.add_edge("retriever", "generator")
    workflow.add_edge("generator", "postprocess")
    workflow.add_edge("postprocess", END)
    return workflow.compile()

app_orchestrator = create_orchestrator()

async def run_agent_orchestration(message: str, history: List[Dict[str, Any]], language: str = "it", visual_context: Optional[str] = None) -> Dict[str, Any]:
    initial_state: AgentState = {
        "message": message, "history": history, "language": language, "visual_context": visual_context,
        "plan": None, "contexts": [], "answer": "", "should_escalate": False, "escalation_reason": None,
        "sources": [], "maps": None
    }
    return await app_orchestrator.ainvoke(initial_state)
