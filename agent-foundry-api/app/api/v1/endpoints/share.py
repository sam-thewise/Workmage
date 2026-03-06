"""Public share endpoints - no auth required for viewing shared run output."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.chain_run import ChainRun
from app.models.run_share_link import RunShareLink

router = APIRouter(prefix="/share", tags=["share"])


@router.get("/run/{token}")
async def get_shared_run_output(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Public: get run output by share token. Returns 404 if token invalid or expired."""
    result = await db.execute(
        select(RunShareLink, ChainRun).where(
            RunShareLink.token == token,
            RunShareLink.run_id == ChainRun.id,
        )
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(404, "Link not found or expired")
    link, run = row[0], row[1]
    if link.expires_at and link.expires_at < datetime.now(timezone.utc):
        raise HTTPException(404, "Link not found or expired")
    return {
        "id": run.id,
        "chain_id": run.chain_id,
        "status": run.status,
        "content": run.content,
        "error": run.error,
        "summary": run.summary,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }
