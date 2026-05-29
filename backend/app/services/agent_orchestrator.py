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
    normalize_text
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

async def planning_node(state: AgentState) -> Dict[str, Any]:
    logger.info("Node: planning")
    message = state["message"]
    history = state["history"]
    visual_context = state.get("visual_context")
    
    if explicit_operator_requested(message):
        return {
            "should_escalate": True,
            "escalation_reason": "human_operator_requested",
            "answer": human_operator_answer(state["language"])
        }
    
    plan = await build_query_plan(message, history)
    
    if visual_context:
        from backend.app.services.rag_service import PlannedRetrievalQuery
        import dataclasses
        anchored_query = f"{visual_context} Giochi del Mediterraneo Taranto 2026 mascotte logo emblema"
        new_queries = list(plan.retrieval_queries)
        new_queries.append(PlannedRetrievalQuery(query=anchored_query, domain="general", weight=1.5))
        new_queries.append(PlannedRetrievalQuery(query=visual_context, domain="general", weight=1.0))
        new_expanded = list(plan.expanded_queries)
        new_expanded.extend([visual_context, anchored_query])
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
        return {
            "answer": unavailable_answer(state["language"]),
            "should_escalate": True,
            "escalation_reason": "no_context"
        }
    
    answer = await build_answer(message, plan, contexts, False, None, state["history"])
    if is_refusal_answer(answer):
        should_escalate = True
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

    norm_ans = robust_normalize(answer)
    initial_sources = []
    seen_urls = set()
    for ctx in contexts:
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
    
    for c in contexts:
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
        "sources": sources[:4],
        "maps": maps
    }

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
