from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.models.base import Base
from app.models.user import User


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
                timezone="Asia/Seoul",
            )
        )
        session.commit()
