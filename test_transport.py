import sys
from pathlib import Path
sys.path.append('.')

from backend.app.services import transport_service
from backend.app.services.rag_service import QueryPlan
from backend.app.repositories.database import init_database
import logging

logging.basicConfig(level=logging.INFO)

# init_database is not strictly needed for connect() but let's make sure
plan = QueryPlan(
    original_query="Quali sono i prossimi bus alla fermata Orsini?",
    retrieval_query="",
    intent="general_information",
    domain="general",
    domains=["general"],
    retrieval_queries=[],
    entities={"transport_stop": "Orsini"},
    response_language="it",
    expanded_queries=[],
    filters=[],
)

print("Is transport query:", transport_service.is_transport_query(plan))

context = transport_service.get_transport_context(plan)
print("CONTEXT:")
print(context)
