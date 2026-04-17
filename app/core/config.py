from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Planner API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://planner:planner@localhost:5432/ai_planner"
    db_connect_timeout_seconds: int = 5
    db_echo: bool = False
    auto_create_tables: bool = False
    seed_demo_user: bool = False
    demo_user_email: str = "demo@example.com"
    demo_user_name: str = "Demo User"
    default_day_start: str = "06:00"
    default_day_end: str = "23:00"
    gemini_api_key: str | None = None
    llm_model: str = "gemini-2.5-flash-lite"
    llm_reasoning_effort: str = "none"
    llm_enable_web_search: bool = False
    llm_web_search_domains: list[str] = Field(default_factory=list)
    allowed_origins: list[str] = Field(default_factory=list)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
