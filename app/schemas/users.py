from datetime import datetime

from pydantic import BaseModel, Field
from pydantic import EmailStr

from app.schemas.base import ORMModel


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    timezone: str = "Asia/Seoul"


class UserRead(ORMModel):
    id: int
    email: EmailStr
    name: str
    timezone: str
    created_at: datetime
    updated_at: datetime
