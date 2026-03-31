from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "NetScout"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production-use-a-long-random-string"
    AGENT_TOKEN: str = "change-me-in-production"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://netscout:netscout@postgres:5432/netscout"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # JWT
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours

    # CORS
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:5173"]

    class Config:
        env_file = ".env"


settings = Settings()
