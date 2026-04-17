from typing import TypeVar

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User

ModelType = TypeVar("ModelType")


def require_user(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")
    return user


def require_owned_resource(
    session: Session,
    model: type[ModelType],
    resource_id: int,
    user_id: int,
    *,
    detail: str,
) -> ModelType:
    require_user(session, user_id)
    resource = session.get(model, resource_id)
    if not resource or getattr(resource, "user_id", None) != user_id:
        raise HTTPException(status_code=404, detail=detail)
    return resource
