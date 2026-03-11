"""Application configuration."""
from pydantic import model_validator
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

    @model_validator(mode="after")
    def add_frontend_url_to_cors(self) -> "Settings":
        if self.FRONTEND_URL and self.FRONTEND_URL.rstrip("/") not in self.CORS_ORIGINS:
            self.CORS_ORIGINS = [*self.CORS_ORIGINS, self.FRONTEND_URL.rstrip("/")]
        return self

    @model_validator(mode="after")
    def derive_async_url_from_sync_if_only_sync_set(self) -> "Settings":
        """If only DATABASE_SYNC_URL is set (e.g. Azure secret), use it for async too to avoid connecting to default postgres:5432."""
        default_async = "postgresql+asyncpg://postgres:postgres@postgres:5432/agentfoundry"
        default_sync = "postgresql://postgres:postgres@postgres:5432/agentfoundry"
        if self.DATABASE_URL == default_async and self.DATABASE_SYNC_URL != default_sync:
            self.DATABASE_URL = self.DATABASE_SYNC_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self
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

    # Mint payment: user-paid Workmage Agent NFT mints
    MINT_PAYMENT_CONTRACT_AVALANCHE: str = ""
    MINT_PAYMENT_CONTRACT_FUJI: str = ""
    AGENT_NFT_MINTER_PRIVATE_KEY: str = ""  # Holds MINTER_ROLE on WorkmageAgentNFT
    MINT_FEE_MARGIN_FACTOR: float = 1.2  # required = gas * gas_price * margin
    MINT_ESTIMATED_GAS: int = 150_000  # Fixed estimate for mint(address) tx
    MINT_INTENT_EXPIRY_HOURS: int = 24

    # X Authority workflow: optional scheduled chain run + draft creation
    # Set X_AUTHORITY_CHAIN_ID and X_AUTHORITY_USER_ID to enable; chain output is parsed and ContentDraft rows created for the user.
    X_AUTHORITY_CHAIN_ID: int = 0  # 0 = disabled
    X_AUTHORITY_USER_ID: int = 0  # User ID to attribute drafts to
    X_AUTHORITY_INPUT: str = ""  # Default input for the chain (e.g. expert handles or "today's trends")
    X_AUTHORITY_MODEL: str = "openai/gpt-5.2"

    # Twitter MCP proxy (twitter-automation service)
    TWITTER_MCP_URL: str = "http://twitter-automation:8010/mcp/twitter"
    TWITTER_MCP_TIMEOUT_SEC: int = 60
    TWITTER_MCP_RETRIES: int = 2
    TWITTER_MCP_HEALTH_PATH: str = "/health"


settings = Settings()
