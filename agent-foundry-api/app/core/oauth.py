"""OAuth 2.0 client for Google, Facebook, and X (Twitter)."""
import secrets

from jose import JWTError, jwt

from app.core.config import settings

try:
    from authlib.integrations.httpx_client import AsyncOAuth2Client
except ImportError:
    AsyncOAuth2Client = None  # authlib/httpx not installed

OAUTH_PROVIDERS = {
    "google": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "scope": "openid email profile",
    },
    "facebook": {
        "auth_url": "https://www.facebook.com/v18.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v18.0/oauth/access_token",
        "userinfo_url": "https://graph.facebook.com/me?fields=id,email,name",
        "client_id": settings.FACEBOOK_APP_ID,
        "client_secret": settings.FACEBOOK_APP_SECRET,
        "scope": "email public_profile",
    },
    "x": {
        "auth_url": "https://twitter.com/i/oauth2/authorize",
        "token_url": "https://api.twitter.com/2/oauth2/token",
        "userinfo_url": "https://api.twitter.com/2/users/me",
        "client_id": settings.X_CLIENT_ID,
        "client_secret": settings.X_CLIENT_SECRET,
        "scope": "tweet.read users.read offline.access",
        "pkce": True,
    },
}


def is_provider_enabled(provider: str) -> bool:
    """Check if OAuth provider is configured."""
    cfg = OAUTH_PROVIDERS.get(provider)
    return bool(cfg and cfg["client_id"] and cfg["client_secret"])


def get_oauth_client(provider: str, redirect_uri: str, code_verifier: str | None = None):
    """Create OAuth2 client for the provider."""
    if AsyncOAuth2Client is None:
        return None
    cfg = OAUTH_PROVIDERS.get(provider)
    if not cfg or not is_provider_enabled(provider):
        return None
    kw = {
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
        "redirect_uri": redirect_uri,
        "scope": cfg.get("scope", "openid email profile"),
    }
    if code_verifier and cfg.get("pkce"):
        kw["code_verifier"] = code_verifier
    return AsyncOAuth2Client(**kw)


def make_oauth_state(code_verifier: str | None = None) -> str:
    """Create signed state param (optionally includes code_verifier for PKCE)."""
    payload = {"s": secrets.token_urlsafe(16)}
    if code_verifier:
        payload["v"] = code_verifier
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def parse_oauth_state(state: str) -> dict:
    """Parse and verify state, return {s, v?}."""
    try:
        return jwt.decode(state, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return {}


async def fetch_user_info(provider: str, token: dict) -> dict | None:
    """Fetch user info from provider after token exchange."""
    if AsyncOAuth2Client is None:
        return None
    cfg = OAUTH_PROVIDERS.get(provider)
    if not cfg:
        return None
    async with AsyncOAuth2Client(
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        token=token,
    ) as client:
        resp = await client.get(cfg["userinfo_url"])
        if resp.status_code != 200:
            return None
        data = resp.json()
        if provider == "google":
            return {
                "id": data.get("sub"),
                "email": data.get("email", "").lower() or None,
                "name": data.get("name"),
            }
        if provider == "facebook":
            return {
                "id": str(data.get("id", "")),
                "email": (data.get("email") or "").lower() or None,
                "name": data.get("name"),
            }
        if provider == "x":
            # X returns { "data": { "id": "...", "username": "..." } } - email needs user.read scope
            ud = data.get("data") or data
            return {
                "id": str(ud.get("id", "")),
                "email": None,  # X OAuth 2.0 often doesn't provide email without additional scope
                "name": ud.get("username"),
            }
    return None
