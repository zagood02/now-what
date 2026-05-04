from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.core.auth import create_access_token, hash_password
from backend.core.config import settings
from backend.db.session import get_db_session
from backend.models.auth_account import AuthAccount
from backend.models.user import User
from backend.schemas.users import GoogleLoginRequest, KakaoLoginRequest, LoginResponse, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
KAKAO_USER_ME_URL = "https://kapi.kakao.com/v2/user/me"


@router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post("/google", response_model=LoginResponse)
def login_with_google(
    payload: GoogleLoginRequest,
    session: Session = Depends(get_db_session),
) -> LoginResponse:
    claims = _verify_google_credential(payload.credential)
    email = claims.get("email")
    if email and claims.get("email_verified") is False:
        raise HTTPException(status_code=401, detail="Google email is not verified.")

    user = _get_or_create_social_user(
        session,
        provider="google",
        provider_user_id=str(claims["sub"]),
        email=email,
        name=claims.get("name") or email or "Google User",
    )
    return _build_login_response(user)


@router.post("/kakao", response_model=LoginResponse)
def login_with_kakao(
    payload: KakaoLoginRequest,
    session: Session = Depends(get_db_session),
) -> LoginResponse:
    profile = _fetch_kakao_profile(payload.access_token)
    kakao_account = profile.get("kakao_account") or {}
    kakao_profile = kakao_account.get("profile") or {}
    email = kakao_account.get("email")

    user = _get_or_create_social_user(
        session,
        provider="kakao",
        provider_user_id=str(profile["id"]),
        email=email,
        name=kakao_profile.get("nickname") or email or "Kakao User",
    )
    return _build_login_response(user)


def _verify_google_credential(credential: str) -> dict:
    if not settings.google_client_id:
        raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID is not configured.")

    try:
        header = jwt.get_unverified_header(credential)
        response = httpx.get(GOOGLE_CERTS_URL, timeout=5)
        response.raise_for_status()
        jwks = response.json()
        key = next(item for item in jwks["keys"] if item["kid"] == header["kid"])
        claims = jwt.decode(
            credential,
            key,
            algorithms=["RS256"],
            audience=settings.google_client_id,
            options={"verify_iss": False},
        )
    except (HTTPException, StopIteration, KeyError, ValueError, JWTError, httpx.HTTPError):
        raise HTTPException(status_code=401, detail="Invalid Google credential.") from None

    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise HTTPException(status_code=401, detail="Invalid Google issuer.")

    return claims


def _fetch_kakao_profile(access_token: str) -> dict:
    try:
        response = httpx.get(
            KAKAO_USER_ME_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=5,
        )
    except httpx.HTTPError:
        raise HTTPException(status_code=401, detail="Could not verify Kakao token.") from None

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid Kakao token.")

    profile = response.json()
    if "id" not in profile:
        raise HTTPException(status_code=401, detail="Kakao profile is missing an id.")
    return profile


def _get_or_create_social_user(
    session: Session,
    *,
    provider: str,
    provider_user_id: str,
    email: str | None,
    name: str,
) -> User:
    existing_account = session.scalar(
        select(AuthAccount).where(
            AuthAccount.provider == provider,
            AuthAccount.provider_user_id == provider_user_id,
        )
    )
    if existing_account:
        return existing_account.user

    user = session.scalar(select(User).where(User.email == email)) if email else None
    if user is None:
        user = User(
            email=email or f"{provider}-{provider_user_id}@oauth.local",
            name=name[:120] or "User",
            timezone="Asia/Seoul",
            hashed_password=hash_password(uuid4().hex),
        )
        session.add(user)
        session.flush()

    session.add(
        AuthAccount(
            user_id=user.id,
            provider=provider,
            provider_user_id=provider_user_id,
            email=email,
            name=name[:120],
        )
    )
    session.commit()
    session.refresh(user)
    return user


def _build_login_response(user: User) -> LoginResponse:
    return LoginResponse(
        access_token=create_access_token(user.id),
        token_type="bearer",
        user=UserRead.model_validate(user),
    )
