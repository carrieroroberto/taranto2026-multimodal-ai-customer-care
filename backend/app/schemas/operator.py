from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr


class OperatorLoginRequestDTO(BaseModel):
    email: str
    password: str


class OperatorDTO(BaseModel):
    id: str
    name: str
    email: str


class LoginResponseDTO(BaseModel):
    access_token: str
    token_type: str = "bearer"
    operator: OperatorDTO


class LogoutResponseDTO(BaseModel):
    status: str = "ok"
    message: str


class TicketStatusUpdateDTO(BaseModel):
    status: Literal["aperto", "chiuso", "open", "closed"]


class ConversationTranslationDTO(BaseModel):
    messages: list[dict]


class EmailDraftDTO(BaseModel):
    subject: str
    body: str
