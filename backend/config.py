from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── Database (Supabase PostgreSQL) ───────────────────────
    # Format: postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
    DATABASE_URL: str = "postgresql+asyncpg://postgres:your-password@db.jqteahtqwffjenserypk.supabase.co:5432/postgres"

    # ── Supabase direct config (optional — for REST API use) ─
    SUPABASE_URL: str = "https://jqteahtqwffjenserypk.supabase.co"
    SUPABASE_SERVICE_KEY: str = ""   # Set via env var — never hardcode

    # ── Redis (use Upstash for serverless, or keep local) ────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Security ─────────────────────────────────────────────
    AGENT_TOKEN: str = "change-me-in-production"
    SECRET_KEY: str = "change-me-in-production"

    # ── App ──────────────────────────────────────────────────
    APP_NAME: str = "NetScout Pro"
    DEBUG: bool = False
    ALLOWED_ORIGINS: list[str] = ["*"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
