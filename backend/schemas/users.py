from datetime import datetime

from pydantic import BaseModel, Field
from pydantic import EmailStr

from backend.schemas.base import ORMModel


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=6)
    timezone: str = "Asia/Seoul"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRead(ORMModel):
    id: int
    email: EmailStr
    name: str
    timezone: str
    created_at: datetime
    updated_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
