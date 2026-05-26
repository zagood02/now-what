from typing import TypeVar

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.db.session import get_db_session
from backend.models.user import User

ModelType = TypeVar("ModelType")
bearer_scheme = HTTPBearer(auto_error=False)


def require_user(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_db_session),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    return require_user(session, user_id)


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
