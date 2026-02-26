"""Admin and moderation endpoints."""
import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_admin_or_moderator, get_admin
from app.db.session import get_db
from app.models.agent import Agent, AgentStatus
from app.models.user import User, UserRole
from app.models.moderator_invite import ModeratorInvite

router = APIRouter(prefix="/admin", tags=["admin"])


# --- Pending agents (admin/mod) ---


@router.get("/agents/pending")
async def list_pending_agents(
    user: User = Depends(get_admin_or_moderator),
    db: AsyncSession = Depends(get_db),
):
    """List agents awaiting moderation."""
    result = await db.execute(
        select(Agent)
        .where(Agent.status == AgentStatus.PENDING_REVIEW.value, Agent.approval_status == "pending")
        .order_by(Agent.created_at.desc())
    )
    agents = result.scalars().all()
    return [{"id": a.id, "name": a.name, "expert_id": a.expert_id, "created_at": a.created_at}]


@router.get("/agents/{agent_id}")
async def get_agent_for_review(
    agent_id: int,
    user: User = Depends(get_admin_or_moderator),
    db: AsyncSession = Depends(get_db),
):
    """Get full agent details for moderation review."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    return {
        "id": agent.id,
        "name": agent.name,
        "description": agent.description,
        "manifest": agent.manifest,
        "price_cents": agent.price_cents,
        "status": agent.status,
        "approval_status": agent.approval_status,
        "expert_id": agent.expert_id,
        "category": agent.category,
        "tags": agent.tags,
        "rejection_reason": agent.rejection_reason,
        "created_at": agent.created_at,
    }


class ApproveRejectBody(BaseModel):
    reason: str | None = None


@router.post("/agents/{agent_id}/approve")
async def approve_agent(
    agent_id: int,
    user: User = Depends(get_admin_or_moderator),
    db: AsyncSession = Depends(get_db),
):
    """Approve agent for listing."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    if agent.status != AgentStatus.PENDING_REVIEW.value or agent.approval_status != "pending":
        raise HTTPException(400, "Agent is not pending approval")
    agent.status = AgentStatus.LISTED.value
    agent.approval_status = "approved"
    agent.moderated_at = datetime.now(timezone.utc)
    agent.moderated_by_id = user.id
    agent.rejection_reason = None
    await db.commit()
    return {"status": "approved"}


@router.post("/agents/{agent_id}/reject")
async def reject_agent(
    agent_id: int,
    body: ApproveRejectBody = ApproveRejectBody(),
    user: User = Depends(get_admin_or_moderator),
    db: AsyncSession = Depends(get_db),
):
    """Reject agent; expert can fix and resubmit."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    if agent.status != AgentStatus.PENDING_REVIEW.value or agent.approval_status != "pending":
        raise HTTPException(400, "Agent is not pending approval")
    agent.status = AgentStatus.REJECTED.value
    agent.approval_status = "rejected"
    agent.moderated_at = datetime.now(timezone.utc)
    agent.moderated_by_id = user.id
    agent.rejection_reason = body.reason
    await db.commit()
    return {"status": "rejected"}


@router.post("/agents/{agent_id}/remove")
async def remove_listed_agent(
    agent_id: int,
    body: ApproveRejectBody = ApproveRejectBody(),
    user: User = Depends(get_admin_or_moderator),
    db: AsyncSession = Depends(get_db),
):
    """Remove an already-listed agent (e.g. policy violation)."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    agent.status = AgentStatus.REJECTED.value
    agent.approval_status = "rejected"
    agent.moderated_at = datetime.now(timezone.utc)
    agent.moderated_by_id = user.id
    agent.rejection_reason = body.reason or "Removed by moderator"
    await db.commit()
    return {"status": "removed"}


# --- Moderator invites (admin only) ---


class InviteModeratorRequest(BaseModel):
    email: EmailStr


INVITE_EXPIRY_DAYS = 7


@router.post("/invites")
async def create_moderator_invite(
    payload: InviteModeratorRequest,
    user: User = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a moderator invite. Admin only."""
    email = payload.email.strip().lower()
    # Check if user already admin/mod
    result = await db.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()
    if existing and existing.role.value in ("admin", "moderator"):
        raise HTTPException(400, "User is already admin or moderator")
    # Check for existing valid invite
    result = await db.execute(
        select(ModeratorInvite)
        .where(ModeratorInvite.email == email, ModeratorInvite.accepted_at.is_(None))
        .where(ModeratorInvite.expires_at > datetime.now(timezone.utc))
    )
    if result.scalars().first():
        raise HTTPException(400, "An active invite already exists for this email")
    token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(days=INVITE_EXPIRY_DAYS)
    invite = ModeratorInvite(
        email=email,
        token=token,
        invited_by_id=user.id,
        expires_at=expires_at,
    )
    db.add(invite)
    await db.commit()
    return {"token": token, "expires_at": expires_at.isoformat(), "email": email}


@router.get("/invites")
async def list_moderator_invites(
    user: User = Depends(get_admin),
    db: AsyncSession = Depends(get_db),
):
    """List moderator invites. Admin only."""
    result = await db.execute(
        select(ModeratorInvite).order_by(ModeratorInvite.created_at.desc())
    )
    invites = result.scalars().all()
    return [
        {
            "id": i.id,
            "email": i.email,
            "expires_at": i.expires_at.isoformat() if i.expires_at else None,
            "accepted_at": i.accepted_at.isoformat() if i.accepted_at else None,
        }
        for i in invites
    ]


class AcceptInviteRequest(BaseModel):
    token: str


@router.post("/invites/accept")
async def accept_moderator_invite(
    payload: AcceptInviteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Accept moderator invite. User must be logged in with the invited email."""
    result = await db.execute(
        select(ModeratorInvite)
        .where(ModeratorInvite.token == payload.token)
        .where(ModeratorInvite.accepted_at.is_(None))
        .where(ModeratorInvite.expires_at > datetime.now(timezone.utc))
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(400, "Invalid or expired invite")
    if user.email.lower() != invite.email.lower():
        raise HTTPException(403, "Invite was sent to a different email address")
    invite.accepted_at = datetime.now(timezone.utc)
    user.role = UserRole.MODERATOR
    await db.commit()
    return {"status": "accepted", "role": "moderator"}
