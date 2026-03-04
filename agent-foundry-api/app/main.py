"""Agent Foundry API - Main application."""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx
from sqlalchemy import select, update

from app.api.v1.router import api_router
from app.api.webhooks import router as webhooks_router
from app.core.config import settings
from app.db.base import AsyncSessionLocal
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

async def promote_admin_emails():
    """Promote users with ADMIN_EMAILS to admin role on startup."""
    emails = [e.strip().lower() for e in settings.ADMIN_EMAILS.split(",") if e.strip()]
    if not emails:
        return
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email.in_(emails)))
        users = result.scalars().all()
        for u in users:
            if u.role != UserRole.ADMIN:
                await db.execute(update(User).where(User.id == u.id).values(role=UserRole.ADMIN))
        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    await promote_admin_emails()
    if settings.TWITTER_MCP_URL:
        try:
            health_url = f"{settings.TWITTER_MCP_URL.rsplit('/mcp/twitter', 1)[0]}{settings.TWITTER_MCP_HEALTH_PATH}"
            with httpx.Client(timeout=max(3, settings.TWITTER_MCP_TIMEOUT_SEC // 2)) as client:
                resp = client.get(health_url)
            if resp.status_code >= 400:
                logger.warning("Twitter automation service health check failed: %s", resp.status_code)
        except Exception as exc:
            logger.warning("Twitter automation service unavailable at startup: %s", exc)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(webhooks_router)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
