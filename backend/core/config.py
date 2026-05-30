from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "AI Planner API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./ai_planner.db"
    db_connect_timeout_seconds: int = 5
    db_pool_pre_ping: bool = True
    db_pool_recycle_seconds: int = 1800
    db_echo: bool = False
    auto_create_tables: bool = False
    seed_demo_user: bool = False
    demo_user_email: str = "demo@example.com"
    demo_user_name: str = "Demo User"
    default_day_start: str = "09:00"
    default_day_end: str = "22:00"
    default_buffer_minutes: int = 30
    default_max_auto_minutes_per_day: int = 360
    gemini_api_key: str | None = None
    google_client_id: str | None = None
    llm_model: str = "gemini-2.5-flash-lite"
    llm_reasoning_effort: str = "none"
    llm_enable_web_search: bool = False
    llm_web_search_domains: list[str] = Field(default_factory=list)
    allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost:3001"])
    jwt_secret_key: str | None = None
    jwt_algorithm: str = "HS256"
    secret_key: str | None = None
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    max_calendar_range_days: int = 370
    max_allocation_range_days: int = 120

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def jwt_signing_key(self) -> str:
        configured_key = (self.jwt_secret_key or self.secret_key or "").strip()
        if configured_key:
            return configured_key
        if self.environment.lower() in {"prod", "production"}:
            raise RuntimeError("JWT_SECRET_KEY must be configured in production.")
        return "dev-only-insecure-jwt-secret"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
