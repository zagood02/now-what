from sqlalchemy import select

from backend.core.config import settings
from backend.core.auth import hash_password
from backend.db.session import SessionLocal, engine
from backend.models.base import Base
from backend.models.user import User


def create_db_and_tables() -> None:
    Base.metadata.create_all(bind=engine)


def seed_demo_user() -> None:
    if not settings.seed_demo_user:
        return

    with SessionLocal() as session:
        existing = session.scalar(select(User).where(User.email == settings.demo_user_email))
        if existing:
            return

        session.add(
            User(
                email=settings.demo_user_email,
                name=settings.demo_user_name,
                hashed_password=hash_password("demo-password"),
                timezone="Asia/Seoul",
            )
        )
        session.commit()
