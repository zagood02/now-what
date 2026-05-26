from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.auth import create_access_token, hash_password, verify_password
from backend.db.session import get_db_session
from backend.models.user import User
from backend.schemas.users import Token, UserCreate, UserLogin, UserRead, LoginResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, session: Session = Depends(get_db_session)) -> User:
    existing = session.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=409, detail="A user with this email already exists.")

    hashed_password = hash_password(payload.password)
    user = User(
        email=payload.email,
        name=payload.name,
        hashed_password=hashed_password,
        timezone=payload.timezone,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.post("/login", response_model=LoginResponse)
def login_user(payload: UserLogin, session: Session = Depends(get_db_session)) -> LoginResponse:
    user = session.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    access_token = create_access_token(user.id)
    return LoginResponse(access_token=access_token, token_type="bearer", user=user)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, session: Session = Depends(get_db_session)) -> User:
    existing = session.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=409, detail="A user with this email already exists.")

    hashed_password = hash_password(payload.password)
    user = User(
        email=payload.email,
        name=payload.name,
        hashed_password=hashed_password,
        timezone=payload.timezone,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.get("", response_model=list[UserRead])
def list_users(session: Session = Depends(get_db_session)) -> list[User]:
    return session.scalars(select(User).order_by(User.id.asc())).all()


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: int, session: Session = Depends(get_db_session)) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return user
