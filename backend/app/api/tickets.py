from fastapi import APIRouter, status

from backend.app.schemas.ticket import TicketRequestDTO
from backend.app.repositories.persistence_repository import save_ticket


router = APIRouter(tags=["tickets"])


@router.post("/tickets", status_code=status.HTTP_201_CREATED)
def post_ticket(ticket: TicketRequestDTO):
    save_ticket(ticket.model_dump())
    return {"status": "ok", "message": "Ticket created", "category": ticket.category}
