from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr


class OperatorLoginRequestDTO(BaseModel):
    email: str
    password: str


class OperatorDTO(BaseModel):
    id: str
    email: str


class LoginResponseDTO(BaseModel):
    access_token: str
    token_type: str = "bearer"
    operator: OperatorDTO


class TicketStatusUpdateDTO(BaseModel):
    status: Literal["open", "in_progress", "closed"]
