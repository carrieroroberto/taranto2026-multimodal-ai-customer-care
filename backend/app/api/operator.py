from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from backend.app.repositories.persistence_repository import (
    get_operator_by_email,
    get_ticket_detail,
    get_tickets,
    update_ticket_status,
)
from backend.app.schemas.operator import (
    LoginResponseDTO,
    OperatorDTO,
    OperatorLoginRequestDTO,
    TicketStatusUpdateDTO,
)
from backend.app.services.auth_service import create_access_token, decode_access_token, verify_password


router = APIRouter(prefix="/operator", tags=["operator"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/operator/login")


async def get_current_operator(token: Annotated[str, Depends(oauth2_scheme)]):
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    email: str = payload.get("sub")
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    operator = get_operator_by_email(email)
    if operator is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Operator not found")
    return operator


@router.post("/login", response_model=LoginResponseDTO)
async def login(request: OperatorLoginRequestDTO):
    operator = get_operator_by_email(request.email)
    if not operator or not verify_password(request.password, operator["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": operator["email"]})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "operator": {
            "id": str(operator["id"]),
            "email": operator["email"]
        }
    }


@router.get("/tickets")
async def list_tickets(
    current_operator: Annotated[dict, Depends(get_current_operator)],
    status: str | None = None,
    priority: str | None = None,
    domain: str | None = None,
):
    return get_tickets(status=status, priority=priority, domain=domain)


@router.get("/tickets/{ticket_id}")
async def ticket_detail(
    ticket_id: str,
    current_operator: Annotated[dict, Depends(get_current_operator)]
):
    detail = get_ticket_detail(ticket_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return detail


@router.patch("/tickets/{ticket_id}/status")
async def patch_ticket_status(
    ticket_id: str,
    update: TicketStatusUpdateDTO,
    current_operator: Annotated[dict, Depends(get_current_operator)]
):
    updated = update_ticket_status(ticket_id, update.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return updated
