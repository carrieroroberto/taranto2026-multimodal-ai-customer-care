from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.repositories.persistence_repository import (
    get_operator_by_email,
    get_ticket_detail,
    get_tickets,
    update_ticket_status,
)
from backend.app.schemas.operator import (
    ConversationTranslationDTO,
    EmailDraftDTO,
    LoginResponseDTO,
    LogoutResponseDTO,
    OperatorDTO,
    OperatorLoginRequestDTO,
    TicketStatusUpdateDTO,
)
from backend.app.services.auth_service import create_access_token, decode_access_token, verify_password
from backend.app.services.llm_service import (
    generate_operator_email_draft,
    translate_operator_conversation,
)


router = APIRouter(prefix="/operator", tags=["operator"])
auth_router = APIRouter(tags=["auth"])

bearer_scheme = HTTPBearer()


async def get_current_operator(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
):
    payload = decode_access_token(credentials.credentials)
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


def authenticate_operator(request: OperatorLoginRequestDTO) -> LoginResponseDTO:
    operator = get_operator_by_email(request.email)
    if not operator or not verify_password(request.password, operator["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": operator["email"]})
    return LoginResponseDTO(
        access_token=access_token,
        token_type="bearer",
        operator={
            "id": str(operator["id"]),
            "name": operator.get("name") or "Roberto",
            "email": operator["email"],
        },
    )


@auth_router.post("/login", response_model=LoginResponseDTO)
async def root_login(request: OperatorLoginRequestDTO):
    return authenticate_operator(request)


@auth_router.post("/logout", response_model=LogoutResponseDTO)
async def root_logout(
    current_operator: Annotated[dict, Depends(get_current_operator)],
):
    return LogoutResponseDTO(
        message=f"Logout successful for {current_operator['email']}. Remove the JWT token from the client.",
    )


@router.post("/login", response_model=LoginResponseDTO)
async def login(request: OperatorLoginRequestDTO):
    return authenticate_operator(request)


@router.post("/logout", response_model=LogoutResponseDTO)
async def logout(
    current_operator: Annotated[dict, Depends(get_current_operator)],
):
    return LogoutResponseDTO(
        message=f"Logout successful for {current_operator['email']}. Remove the JWT token from the client.",
    )


@router.get("/me", response_model=OperatorDTO)
async def me(current_operator: Annotated[dict, Depends(get_current_operator)]):
    return OperatorDTO(
        id=str(current_operator["id"]),
        name=current_operator.get("name") or "Roberto",
        email=current_operator["email"],
    )


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


@router.post(
    "/tickets/{ticket_id}/translate",
    response_model=ConversationTranslationDTO,
)
async def translate_ticket_conversation(
    ticket_id: str,
    current_operator: Annotated[dict, Depends(get_current_operator)]
):
    detail = get_ticket_detail(ticket_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ConversationTranslationDTO(
        messages=await translate_operator_conversation(detail.get("conversation") or [])
    )


@router.post(
    "/tickets/{ticket_id}/email-draft",
    response_model=EmailDraftDTO,
)
async def ticket_email_draft(
    ticket_id: str,
    current_operator: Annotated[dict, Depends(get_current_operator)]
):
    detail = get_ticket_detail(ticket_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Ticket not found")
    draft = await generate_operator_email_draft(detail, current_operator)
    return EmailDraftDTO(**draft)


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
