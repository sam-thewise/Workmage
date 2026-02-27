"""Application configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    PROJECT_NAME: str = "Workmage"
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/agentfoundry"
    DATABASE_SYNC_URL: str = "postgresql://postgres:postgres@postgres:5432/agentfoundry"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Auth
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000", "http://frontend:5173"]

    # Stripe (optional - set for paid purchases)
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    FRONTEND_URL: str = "http://localhost:5173"
    API_PUBLIC_URL: str = "http://localhost:8000"  # For OAuth callbacks; must be reachable from browser

    # Platform LLM keys (for platform-hosted runs when user doesn't use BYOK)
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # When production, sanitize error messages to avoid exposing internals
    ENVIRONMENT: str = "development"

    # OAuth (optional - set client IDs/secrets to enable)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    FACEBOOK_APP_ID: str = ""
    FACEBOOK_APP_SECRET: str = ""
    X_CLIENT_ID: str = ""
    X_CLIENT_SECRET: str = ""

    # Admin: comma-separated emails promoted to admin on startup
    ADMIN_EMAILS: str = ""


settings = Settings()
