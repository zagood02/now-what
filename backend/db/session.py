from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import settings


def _build_engine():
    connect_args: dict[str, object] = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    elif settings.database_url.startswith("postgresql"):
        # Fail fast when Postgres is down instead of hanging for minutes.
        connect_args["connect_timeout"] = settings.db_connect_timeout_seconds

    return create_engine(
        settings.database_url,
        echo=settings.db_echo,
        future=True,
        connect_args=connect_args,
        pool_pre_ping=settings.db_pool_pre_ping,
        pool_recycle=settings.db_pool_recycle_seconds,
    )


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
