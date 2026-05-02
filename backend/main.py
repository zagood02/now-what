from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.router import api_router
from backend.core.config import settings
from backend.db.init_db import create_db_and_tables, seed_demo_user

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.auto_create_tables:
        try:
            create_db_and_tables()
            seed_demo_user()
        except Exception as exc:  # pragma: no cover - startup fallback
            logger.warning("Database startup initialization skipped: %s", exc)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "AI planner backend with schedule management, auto-allocation, and goal-based planning.\n\n"
        "Demo pages:\n"
        "- [Goal Q&A flow](/api/v1/demo/user-flow)\n"
        "- [API playground](/api/v1/demo/goal-intake)\n"
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "api_prefix": settings.api_v1_prefix,
        "demo_user_flow": "/api/v1/demo/user-flow",
        "demo_api_playground": "/api/v1/demo/goal-intake",
    }
