import logging
import re
from datetime import datetime
from typing import Any

from backend.app.repositories import transport_repository
from backend.app.services.rag_service import QueryPlan

logger = logging.getLogger(__name__)

def get_transport_context(plan: QueryPlan) -> str | None:
    """
    Analyzes the query plan and fetches relevant transport data from SQL.
    Returns a formatted string to be included in the LLM prompt.
    """
    if not is_transport_query(plan):
        return None

    # Try to extract a stop name or route from entities or the query itself
    # Prioritize the new 'transport_stop' entity
    stop_name = plan.entities.get("transport_stop") or plan.entities.get("venue") or plan.entities.get("city")
    
    # If no specific stop entity, try to extract it from the original query
    if not stop_name:
        # We try to clean up the query to find just the stop name
        # If it's something like "fermata Orsini", we want just "Orsini"
        match = re.search(r"fermata\s+([a-zA-Z0-9\s]+)", plan.original_query, re.IGNORECASE)
        if match:
            stop_name = match.group(1).strip()
        else:
            stop_name = plan.original_query

    transport_info = []
    
    # Get current time for real-time filtering
    now = datetime.now()
    current_time_str = now.strftime("%H:%M:%S")

    # 1. Search for stops
    stops = transport_repository.search_transport_info(stop_name)
    if stops:
        info_block = "Fermate trovate:\n"
        for stop in stops:
            info_block += f"- {stop['stop_name']} (ID: {stop['stop_id']})\n"
            
            # 2. For each stop, get some upcoming times starting from now
            times = transport_repository.get_stop_times_by_stop_name(stop['stop_name'], current_time_str)
            if times:
                info_block += f"  Prossimi transiti (dalle ore {current_time_str}):\n"
                for t in times:
                    info_block += f"    * Linea {t['route_short_name']} ({t['trip_headsign']}): arr. {t['arrival_time']}, part. {t['departure_time']}\n"
            else:
                info_block += f"  Nessun transito previsto dopo le {current_time_str} per questa fermata.\n"
        transport_info.append(info_block)

    # 3. Search for routes if mentioned
    # (Optional enhancement: extract route numbers like '1/2', '3', etc.)

    if not transport_info:
        return None

    return "\n\n### INFORMAZIONI TRASPORTI (SQL DB):\n" + "\n".join(transport_info)

def is_transport_query(plan: QueryPlan) -> bool:
    """Checks if the query plan relates to transport."""
    transport_keywords = {"mobilita", "trasporti", "autobus", "bus", "linea", "fermata", "orari", "percorso", "pullman"}
    
    # Check if transport_stop entity was identified
    if plan.entities.get("transport_stop"):
        return True

    # Check domains
    if "venue" in plan.domains or plan.domain == "venue":
        # Venue often implies transport, but we check if transport keywords are in the query
        normalized_query = plan.original_query.lower()
        if any(kw in normalized_query for kw in transport_keywords):
            return True
            
    # Check if 'trasporti' or similar is mentioned in any retrieval query
    for rq in plan.retrieval_queries:
        if any(kw in rq.query.lower() for kw in transport_keywords):
            return True
            
    return False
