"""Saved outputs API: list, get, put, delete by slug (per user)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from pydantic import BaseModel, Field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.user_personality import UserPersonalityProfile
from app.models.saved_output import SavedOutput

router = APIRouter(prefix="/saved-outputs", tags=["saved-outputs"])


class SavedOutputListItem(BaseModel):
    slug: str
    updated_at: str | None
    preview: str | None


class SavedOutputResponse(BaseModel):
    slug: str
    content: str
    updated_at: str | None
    source_chain_run_id: str | None
    source_node_id: str | None
    source_agent_id: int | None


class SavedOutputPut(BaseModel):
    content: str = Field(..., min_length=1)
    source_chain_run_id: str | None = Field(None, max_length=64)
    source_node_id: str | None = Field(None, max_length=64)
    source_agent_id: int | None = None


def _slug_valid(slug: str) -> bool:
    if not slug or len(slug) > 120:
        return False
    return slug.replace("_", "").replace("-", "").isalnum()


@router.get("", response_model=list[SavedOutputListItem])
async def list_saved_outputs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List current user's saved outputs (slug, updated_at, preview)."""
    result = await db.execute(
        select(SavedOutput).where(SavedOutput.user_id == user.id).order_by(SavedOutput.updated_at.desc())
    )
    rows = result.scalars().all()
    return [
        SavedOutputListItem(
            slug=r.slug,
            updated_at=r.updated_at.isoformat() if r.updated_at else None,
            preview=(r.content[:200] + "…") if r.content and len(r.content) > 200 else (r.content or None),
        )
        for r in rows
    ]


@router.get("/{slug}", response_model=SavedOutputResponse)
async def get_saved_output(
    slug: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get one saved output by slug (owner only)."""
    if not _slug_valid(slug):
        raise HTTPException(400, "Invalid slug")
    result = await db.execute(
        select(SavedOutput).where(
            SavedOutput.user_id == user.id,
            SavedOutput.slug == slug,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Saved output not found")
    return SavedOutputResponse(
        slug=row.slug,
        content=row.content,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
        source_chain_run_id=row.source_chain_run_id,
        source_node_id=row.source_node_id,
        source_agent_id=row.source_agent_id,
    )


@router.put("/{slug}", response_model=SavedOutputResponse)
async def put_saved_output(
    slug: str,
    payload: SavedOutputPut,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update saved output by slug."""
    if not _slug_valid(slug):
        raise HTTPException(400, "Invalid slug")
    result = await db.execute(
        select(SavedOutput).where(
            SavedOutput.user_id == user.id,
            SavedOutput.slug == slug,
        )
    )
    row = result.scalar_one_or_none()
    if row:
        row.content = payload.content
        if payload.source_chain_run_id is not None:
            row.source_chain_run_id = payload.source_chain_run_id
        if payload.source_node_id is not None:
            row.source_node_id = payload.source_node_id
        if payload.source_agent_id is not None:
            row.source_agent_id = payload.source_agent_id
    else:
        row = SavedOutput(
            user_id=user.id,
            slug=slug,
            content=payload.content,
            source_chain_run_id=payload.source_chain_run_id,
            source_node_id=payload.source_node_id,
            source_agent_id=payload.source_agent_id,
        )
        db.add(row)
    await db.commit()
    await db.refresh(row)
    return SavedOutputResponse(
        slug=row.slug,
        content=row.content,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
        source_chain_run_id=row.source_chain_run_id,
        source_node_id=row.source_node_id,
        source_agent_id=row.source_agent_id,
    )


@router.delete("/{slug}", status_code=204)
async def delete_saved_output(
    slug: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete saved output by slug (owner only)."""
    if not _slug_valid(slug):
        raise HTTPException(400, "Invalid slug")
    result = await db.execute(
        select(SavedOutput).where(
            SavedOutput.user_id == user.id,
            SavedOutput.slug == slug,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Saved output not found")
    await db.delete(row)
    await db.commit()
    return None
