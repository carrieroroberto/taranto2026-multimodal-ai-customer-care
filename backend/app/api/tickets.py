import re
import logging
from fastapi import APIRouter, HTTPException, status

from backend.app.schemas.ticket import TicketRequestDTO
from backend.app.repositories.persistence_repository import save_ticket, ensure_conversation
from backend.app.services.ticket_service import generate_ticket_triage


router = APIRouter(tags=["tickets"])
logger = logging.getLogger(__name__)


EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"


@router.post("/tickets", status_code=status.HTTP_201_CREATED)
def post_ticket(ticket: TicketRequestDTO):
    logger.info("RECEIVED TICKET REQUEST: %s", ticket.model_dump_json())
    
    # Validate email
    if not re.match(EMAIL_REGEX, ticket.user_email):
        logger.warning("INVALID EMAIL: %s", ticket.user_email)
        raise HTTPException(status_code=400, detail="Invalid email address.")
    
    # Ensure conversation exists
    ensure_conversation(conversation_id=ticket.conversation_id)

    # Generate triage
    triage = generate_ticket_triage(ticket.conversation_id)
    
    # Combine data
    ticket_data = {
        "conversation_id": ticket.conversation_id,
        "user_email": ticket.user_email,
        "domain": triage["domain"],
        "priority": triage["priority"],
        "summary": triage["summary"],
        "original_message": triage["original_message"],
        "translated_message": triage["translated_message"],
    }
    
    logger.info("SAVING TICKET TO DATABASE: %s", ticket_data)
    
    try:
        created_ticket = save_ticket(ticket_data)
        logger.info("TICKET SAVED SUCCESSFULLY WITH ID: %s", created_ticket.get("id"))
    except ValueError as exc:
        logger.error("DATABASE SAVE FAILED: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "ok",
        "message": "Ticket created and sent to operator",
        "ticket": created_ticket,
    }
