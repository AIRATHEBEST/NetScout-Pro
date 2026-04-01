from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── Database (Supabase PostgreSQL) ───────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:your-password@db.jqteahtqwffjenserypk.supabase.co:5432/postgres"

    # ── Supabase ─────────────────────────────────────────────
    SUPABASE_URL: str = "https://jqteahtqwffjenserypk.supabase.co"
    SUPABASE_SERVICE_KEY: str = ""

    # ── Redis ─────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Security ──────────────────────────────────────────────
    AGENT_TOKEN: str = "change-me-in-production"
    SECRET_KEY: str = "change-me-in-production"

    # ── App ───────────────────────────────────────────────────
    APP_NAME: str = "NetScout Pro"
    DEBUG: bool = False
    ALLOWED_ORIGINS: str = "*"

    @property
    def CORS_ORIGINS(self) -> list[str]:
        if self.ALLOWED_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# Module-level singleton so `from config import settings` works
settings = get_settings()
