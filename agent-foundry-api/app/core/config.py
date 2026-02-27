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
    # Optional: MCP endpoint URL for manifests (e.g. if API is behind different domain). If unset, use API_PUBLIC_URL + API_V1_STR + "/mcp"
    MCP_PUBLIC_URL: str = ""

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

    # Action infrastructure + rollout controls
    ACTIONS_ENABLE_LIVE_TX: bool = False
    ACTIONS_ENABLE_REFERENCE_CAPABILITIES: bool = True
    ACTIONS_HTTP_TIMEOUT_SEC: int = 15
    ACTIONS_DEFAULT_MAX_SPEND_WEI: int = 100000000000000000  # 0.1 AVAX default
    ACTIONS_DEFAULT_MAX_GAS_WEI: int = 3000000000000000
    ACTIONS_MIN_TRUST_SCORE: int = 20
    ACTIONS_FACTORY_ADDRESSES: str = ""

    # Avalanche/Snowtrace integration
    AVALANCHE_RPC_URL: str = ""
    AVALANCHE_FUJI_RPC_URL: str = ""
    SNOWTRACE_API_URL: str = "https://api.routescan.io/v2/network/mainnet/evm/etherscan/api"
    SNOWTRACE_FUJI_API_URL: str = "https://api.routescan.io/v2/network/testnet/evm/43113/etherscan/api"
    SNOWTRACE_API_KEY: str = ""

    # Signer: private key(s) for agent wallets. Never commit real keys.
    # Single key for all agent wallets (testing) or JSON map: {"0xAddr": "0xhexkey", ...}
    AGENT_SIGNER_PRIVATE_KEY: str = ""
    AGENT_SIGNER_KEYS: str = ""  # JSON object wallet_address -> hex_private_key
    # Optional base64 Fernet key for encrypting platform-managed signer keys. If unset, derived from SECRET_KEY + salt.
    SIGNER_ENCRYPTION_KEY: str = ""
    ACTIONS_REQUIRE_APPROVAL_FOR_LIVE: bool = True


settings = Settings()
