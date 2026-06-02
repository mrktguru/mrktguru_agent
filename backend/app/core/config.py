"""Application configuration loaded from environment."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    ENVIRONMENT: str = "development"
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"

    # Anthropic
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://appforge:appforge@postgres:5432/appforge"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Security
    SECRET_KEY: str = "change-me"
    FERNET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # SSH
    PLATFORM_SSH_KEY_PATH: str = "/app/keys/platform_key"

    # Backups (on the target site server). Persistent dir survives reboots; /tmp does not.
    SITEDOC_BACKUP_DIR: str = "/var/lib/sitedoc/backups"
    SITEDOC_BACKUP_RETENTION_DAYS: int = 30

    # Google OAuth (optional)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""  # e.g. https://mrktguru.ru/api/auth/google/callback


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
