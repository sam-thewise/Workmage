"""Content drafts API for X/social approval flow (list, create, edit, approve)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.content_draft import ContentDraft
from app.models.user import User

router = APIRouter(prefix="/content-drafts", tags=["content-drafts"])


class ContentDraftCreate(BaseModel):
    type: str = Field(..., pattern="^(post|reply)$")
    body: str = Field(..., min_length=1)
    target_handle: str | None = Field(None, max_length=120)
    target_url: str | None = Field(None, max_length=512)
    source_chain_run_id: str | None = Field(None, max_length=64)


class ContentDraftBulkItem(BaseModel):
    type: str = Field(..., pattern="^(post|reply)$")
    body: str = Field(..., min_length=1)
    target_handle: str | None = Field(None, max_length=120)
    target_url: str | None = Field(None, max_length=512)


class ContentDraftBulkCreate(BaseModel):
    drafts: list[ContentDraftBulkItem] = Field(..., min_length=1, max_length=50)
    source_chain_run_id: str | None = Field(None, max_length=64)


class ContentDraftUpdate(BaseModel):
    body: str = Field(..., min_length=1)


class ContentDraftListResponse(BaseModel):
    id: int
    type: str
    body: str
    target_handle: str | None
    target_url: str | None
    status: str
    edited_body: str | None
    approved_at: str | None
    created_at: str
    updated_at: str


def _draft_to_item(d: ContentDraft) -> dict:
    return {
        "id": d.id,
        "type": d.type,
        "body": d.body,
        "target_handle": d.target_handle,
        "target_url": d.target_url,
        "source_chain_run_id": d.source_chain_run_id,
        "status": d.status,
        "edited_body": d.edited_body,
        "approved_at": d.approved_at.isoformat() if d.approved_at else None,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }


@router.post("", status_code=201)
async def create_draft(
    payload: ContentDraftCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a content draft (post or reply). Can be created from chain output or manually."""
    draft = ContentDraft(
        user_id=user.id,
        type=payload.type,
        body=payload.body,
        target_handle=payload.target_handle,
        target_url=payload.target_url,
        source_chain_run_id=payload.source_chain_run_id,
        status="draft",
    )
    db.add(draft)
    await db.commit()
    await db.refresh(draft)
    return _draft_to_item(draft)


@router.post("/bulk", status_code=201)
async def create_drafts_bulk(
    payload: ContentDraftBulkCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create multiple drafts from chain/agent output (e.g. parsed posts and replies)."""
    created = []
    for item in payload.drafts:
        draft = ContentDraft(
            user_id=user.id,
            type=item.type,
            body=item.body,
            target_handle=item.target_handle,
            target_url=item.target_url,
            source_chain_run_id=payload.source_chain_run_id,
            status="draft",
        )
        db.add(draft)
        created.append(draft)
    await db.commit()
    for d in created:
        await db.refresh(d)
    return [_draft_to_item(d) for d in created]


@router.get("")
async def list_drafts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    status: str | None = Query(None, description="Filter by status"),
    type_filter: str | None = Query(None, alias="type", description="Filter by type: post or reply"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List current user's content drafts."""
    q = select(ContentDraft).where(ContentDraft.user_id == user.id)
    if status:
        q = q.where(ContentDraft.status == status)
    if type_filter:
        q = q.where(ContentDraft.type == type_filter)
    q = q.order_by(ContentDraft.updated_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    drafts = result.scalars().all()
    return [_draft_to_item(d) for d in drafts]


@router.get("/{draft_id}")
async def get_draft(
    draft_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single draft by id (owner only)."""
    draft = (
        await db.execute(
            select(ContentDraft).where(ContentDraft.id == draft_id, ContentDraft.user_id == user.id)
        )
    ).scalar_one_or_none()
    if not draft:
        raise HTTPException(404, "Draft not found")
    return _draft_to_item(draft)


@router.patch("/{draft_id}")
async def update_draft(
    draft_id: int,
    payload: ContentDraftUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Edit draft body. Only when status is draft or pending_approval."""
    draft = (
        await db.execute(
            select(ContentDraft).where(ContentDraft.id == draft_id, ContentDraft.user_id == user.id)
        )
    ).scalar_one_or_none()
    if not draft:
        raise HTTPException(404, "Draft not found")
    if draft.status not in ("draft", "pending_approval"):
        raise HTTPException(400, f"Cannot edit draft with status {draft.status}")
    draft.edited_body = draft.body
    draft.body = payload.body
    await db.commit()
    await db.refresh(draft)
    return _draft_to_item(draft)


@router.post("/{draft_id}/submit")
async def submit_draft(
    draft_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark draft as pending_approval (optional step before approve)."""
    draft = (
        await db.execute(
            select(ContentDraft).where(ContentDraft.id == draft_id, ContentDraft.user_id == user.id)
        )
    ).scalar_one_or_none()
    if not draft:
        raise HTTPException(404, "Draft not found")
    if draft.status != "draft":
        raise HTTPException(400, f"Draft status is {draft.status}; only draft can be submitted")
    draft.status = "pending_approval"
    await db.commit()
    await db.refresh(draft)
    return _draft_to_item(draft)


@router.post("/{draft_id}/approve")
async def approve_draft(
    draft_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve draft (ready to use / copy to X). Sets status to approved and approved_at."""
    draft = (
        await db.execute(
            select(ContentDraft).where(ContentDraft.id == draft_id, ContentDraft.user_id == user.id)
        )
    ).scalar_one_or_none()
    if not draft:
        raise HTTPException(404, "Draft not found")
    if draft.status not in ("draft", "pending_approval"):
        raise HTTPException(400, f"Draft status is {draft.status}; cannot approve")
    draft.status = "approved"
    draft.approved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(draft)
    return _draft_to_item(draft)


@router.post("/{draft_id}/reject")
async def reject_draft(
    draft_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reject draft (will not be used)."""
    draft = (
        await db.execute(
            select(ContentDraft).where(ContentDraft.id == draft_id, ContentDraft.user_id == user.id)
        )
    ).scalar_one_or_none()
    if not draft:
        raise HTTPException(404, "Draft not found")
    if draft.status not in ("draft", "pending_approval"):
        raise HTTPException(400, f"Draft status is {draft.status}; cannot reject")
    draft.status = "rejected"
    await db.commit()
    await db.refresh(draft)
    return _draft_to_item(draft)
