"""Agent Foundry API - Main application."""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, update

from app.api.v1.router import api_router
from app.api.webhooks import router as webhooks_router
from app.core.config import settings
from app.db.base import AsyncSessionLocal
from app.models.user import User, UserRole
from app.services.twitter_source import get_twitter_source_service

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
    try:
        get_twitter_source_service().startup_validate()
    except Exception as exc:
        logger.warning("Twitter source startup validation failed: %s", exc)
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
