"""Auth endpoints."""
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.oauth import (
    OAUTH_PROVIDERS,
    fetch_user_info,
    get_oauth_client,
    is_provider_enabled,
    make_oauth_state,
    parse_oauth_state,
)
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.models.subscription import Subscription
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserLogin, UserResponse, Token

router = APIRouter(prefix="/auth", tags=["auth"])
TIER_RUNS = {"free": 5, "standard": 50, "pro": 200}


@router.post("/register", response_model=UserResponse)
async def register(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Register a new user."""
    from app.models.user import User

    result = await db.execute(
        select(User).where(User.email == user_in.email.lower())
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    user = User(
        email=user_in.email.lower(),
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    if user_in.role.value == "buyer":
        sub = Subscription(
            buyer_id=user.id,
            tier="free",
            runs_per_period=TIER_RUNS["free"],
            period="monthly",
        )
        db.add(sub)
        await db.commit()
    return user


@router.post("/login", response_model=Token)
async def login(
    login_in: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Login and return JWT token."""
    result = await db.execute(
        select(User).where(User.email == login_in.email.lower())
    )
    user = result.scalar_one_or_none()
    if not user or not user.hashed_password or not verify_password(login_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    access_token = create_access_token(subject=str(user.id))
    return Token(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)) -> User:
    """Get current user."""
    return user


# --- OAuth ---

def _oauth_redirect_uri(provider: str) -> str:
    """Build backend callback URL for OAuth provider (must be reachable from user's browser)."""
    base = settings.API_PUBLIC_URL.rstrip("/")
    return f"{base}{settings.API_V1_STR}/auth/{provider}/callback"


@router.get("/oauth/providers")
async def oauth_providers():
    """Return which OAuth providers are enabled."""
    return {
        "google": is_provider_enabled("google"),
        "facebook": is_provider_enabled("facebook"),
        "x": is_provider_enabled("x"),
    }


@router.get("/{provider}/start")
async def oauth_start(provider: str):
    """Redirect to OAuth provider. provider in (google, facebook, x)."""
    if provider not in ("google", "facebook", "x"):
        raise HTTPException(status_code=404, detail="Unknown provider")
    if not is_provider_enabled(provider):
        raise HTTPException(status_code=400, detail="OAuth provider not configured")
    import secrets
    from authlib.oauth2.rfc7636 import create_s256_code_challenge

    cfg = OAUTH_PROVIDERS[provider]
    redirect_uri = _oauth_redirect_uri(provider)
    code_verifier = None
    if cfg.get("pkce"):
        code_verifier = secrets.token_urlsafe(64)
    state = make_oauth_state(code_verifier)
    params = {
        "response_type": "code",
        "client_id": cfg["client_id"],
        "redirect_uri": redirect_uri,
        "scope": cfg.get("scope", "openid email profile"),
        "state": state,
    }
    if code_verifier:
        params["code_challenge"] = create_s256_code_challenge(code_verifier)
        params["code_challenge_method"] = "S256"
    auth_url = cfg["auth_url"] + "?" + urlencode(params)
    return RedirectResponse(url=auth_url)


@router.get("/{provider}/callback")
async def oauth_callback(provider: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Handle OAuth callback, create/find user, redirect to frontend with token."""
    if provider not in ("google", "facebook", "x"):
        raise HTTPException(status_code=404, detail="Unknown provider")
    if not is_provider_enabled(provider):
        raise HTTPException(status_code=400, detail="OAuth provider not configured")
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code or not state:
        return _redirect_login_error("Missing code or state")
    parsed = parse_oauth_state(state)
    if not parsed:
        return _redirect_login_error("Invalid state")
    code_verifier = parsed.get("v") if OAUTH_PROVIDERS[provider].get("pkce") else None
    redirect_uri = _oauth_redirect_uri(provider)
    client = get_oauth_client(provider, redirect_uri, code_verifier)
    if not client:
        return _redirect_login_error("OAuth client init failed")
    try:
        token = await client.fetch_token(
            OAUTH_PROVIDERS[provider]["token_url"],
            code=code,
            redirect_uri=redirect_uri,
        )
    except Exception:
        return _redirect_login_error("Token exchange failed")
    user_info = await fetch_user_info(provider, token)
    if not user_info or not user_info.get("id"):
        return _redirect_login_error("Could not fetch user info")
    oauth_id = str(user_info["id"])
    email = (user_info.get("email") or "").strip().lower()
    name = user_info.get("name")
    if not email and provider == "x":
        email = f"{oauth_id}@oauth.x.local"
    if not email:
        return _redirect_login_error("Provider did not return email")
    result = await db.execute(
        select(User).where(User.oauth_provider == provider, User.oauth_id == oauth_id)
    )
    user = result.scalar_one_or_none()
    if user:
        pass
    else:
        result2 = await db.execute(select(User).where(User.email == email))
        existing = result2.scalar_one_or_none()
        if existing:
            if existing.oauth_provider and existing.oauth_id:
                return _redirect_login_error("Email already linked to another account")
            existing.oauth_provider = provider
            existing.oauth_id = oauth_id
            user = existing
            await db.commit()
            await db.refresh(user)
        else:
            user = User(
                email=email,
                hashed_password=None,
                oauth_provider=provider,
                oauth_id=oauth_id,
                role=UserRole.BUYER,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            sub = Subscription(buyer_id=user.id, tier="free", runs_per_period=TIER_RUNS["free"], period="monthly")
            db.add(sub)
            await db.commit()
    access_token = create_access_token(subject=str(user.id))
    callback_url = f"{settings.FRONTEND_URL.rstrip('/')}/auth/callback?token={access_token}"
    return RedirectResponse(url=callback_url)


def _redirect_login_error(msg: str):
    """Redirect to frontend login with error in query."""
    url = f"{settings.FRONTEND_URL.rstrip('/')}/login?oauth_error={__import__('urllib.parse').quote(msg)}"
    return RedirectResponse(url=url)
