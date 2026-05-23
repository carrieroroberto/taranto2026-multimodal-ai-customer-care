from fastapi import APIRouter, HTTPException, status

from backend.app.schemas.ticket import TicketRequestDTO
from backend.app.repositories.persistence_repository import save_ticket


router = APIRouter(tags=["tickets"])


@router.post("/tickets", status_code=status.HTTP_201_CREATED)
def post_ticket(ticket: TicketRequestDTO):
    try:
        created_ticket = save_ticket(ticket.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "ok",
        "message": "Ticket created",
        "ticket": created_ticket,
    }
