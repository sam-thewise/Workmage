"""Agents endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_optional
from app.db.session import get_db
from app.models.agent import Agent, AgentStatus
from app.models.user import User
from app.schemas.agent import (
    AgentCreate,
    AgentListResponse,
    AgentResponse,
    AgentUpdate,
)
from app.services.manifest_validator import ManifestValidationError, validate_and_parse

router = APIRouter(prefix="/agents", tags=["agents"])


class ValidateManifestRequest(BaseModel):
    raw: str


@router.post("/validate")
async def validate_manifest(body: ValidateManifestRequest):
    """Validate OASF manifest (public - for preview before create)."""
    try:
        manifest, metadata = validate_and_parse(body.raw)
        return {"valid": True, "manifest": manifest, "metadata": metadata}
    except ManifestValidationError as e:
        return {"valid": False, "errors": e.errors}


@router.get("/", response_model=list[AgentListResponse])
async def list_agents(
    db: AsyncSession = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
    category: str | None = None,
):
    """List agents (public - approved and listed only)."""
    q = select(Agent).where(
        Agent.status == AgentStatus.LISTED.value,
        Agent.approval_status == "approved",
    )
    if category:
        q = q.where(Agent.category == category)
    q = q.order_by(Agent.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    agents = result.scalars().all()
    return agents


@router.get("/my", response_model=list[AgentListResponse])
async def list_my_agents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List current user's agents (experts only)."""
    if user.role.value != "expert":
        raise HTTPException(403, "Experts only")
    result = await db.execute(select(Agent).where(Agent.expert_id == user.id).order_by(Agent.created_at.desc()))
    agents = result.scalars().all()
    return agents


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: int,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Get agent by ID (public for listed; expert for own drafts)."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    if agent.status in (AgentStatus.DRAFT.value, AgentStatus.PENDING_REVIEW.value, AgentStatus.REJECTED.value):
        if not user or user.id != agent.expert_id:
            raise HTTPException(404, "Agent not found")
    return agent


def _build_agent_uri_services(agent_id: int) -> list[dict]:
    """Build ERC-8004 services array for this agent (API, MCP endpoint)."""
    from app.core.config import settings

    base = (settings.API_PUBLIC_URL or "").rstrip("/")
    services = []
    if base:
        services.append({"type": "api", "url": f"{base}/api/v1/agents/{agent_id}"})
        services.append({"type": "agent-uri", "url": f"{base}/api/v1/agents/{agent_id}/agent-uri"})
    # MCP URL if we expose one per agent (optional)
    if base:
        services.append({"type": "mcp", "url": f"{base}/api/v1/agents/{agent_id}/mcp"})
    return services


@router.get("/{agent_id}/agent-uri")
async def get_agent_uri(
    agent_id: int,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """ERC-8004 AgentURI metadata for on-chain identity (name, description, image, services). Public for listed agents."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    if agent.status in (AgentStatus.DRAFT.value, AgentStatus.PENDING_REVIEW.value, AgentStatus.REJECTED.value):
        if not user or user.id != agent.expert_id:
            raise HTTPException(404, "Agent not found")

    manifest = agent.manifest or {}
    # Optional image from manifest (avatar, image, icon)
    image = (
        manifest.get("avatar")
        or manifest.get("image")
        or (manifest.get("metadata") or {}).get("image")
        or (manifest.get("metadata") or {}).get("avatar")
    )
    if isinstance(image, dict):
        image = image.get("url") or image.get("href")
    if not isinstance(image, str):
        image = None

    return {
        "name": agent.name,
        "description": agent.description or "",
        "image": image,
        "services": _build_agent_uri_services(agent_id),
    }


@router.post("/", response_model=AgentResponse)
async def create_agent(
    payload: AgentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create agent (experts only)."""
    if user.role.value != "expert":
        raise HTTPException(403, "Experts only")
    try:
        manifest, metadata = validate_and_parse(payload.manifest_raw)
    except ManifestValidationError as e:
        raise HTTPException(400, detail={"message": "Invalid manifest", "errors": e.errors}) from e

    agent = Agent(
        expert_id=user.id,
        name=payload.name or metadata.get("name") or "Unnamed Agent",
        description=payload.description or metadata.get("description"),
        manifest=manifest,
        price_cents=payload.price_cents,
        status=AgentStatus.DRAFT.value,
        category=payload.category,
        tags=payload.tags,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: int,
    payload: AgentUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update agent (expert owner only)."""
    if user.role.value != "expert":
        raise HTTPException(403, "Experts only")
    result = await db.execute(select(Agent).where(Agent.id == agent_id, Agent.expert_id == user.id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")

    if payload.manifest_raw is not None:
        try:
            manifest, metadata = validate_and_parse(payload.manifest_raw)
            agent.manifest = manifest
            if payload.name is None and metadata.get("name"):
                agent.name = metadata["name"]
            if payload.description is None and metadata.get("description"):
                agent.description = metadata["description"]
        except ManifestValidationError as e:
            raise HTTPException(400, detail={"message": "Invalid manifest", "errors": e.errors}) from e

    if payload.name is not None:
        agent.name = payload.name
    if payload.description is not None:
        agent.description = payload.description
    if payload.price_cents is not None:
        agent.price_cents = payload.price_cents
    if payload.category is not None:
        agent.category = payload.category
    if payload.tags is not None:
        agent.tags = payload.tags

    await db.commit()
    await db.refresh(agent)
    return agent


@router.patch("/{agent_id}/publish")
async def publish_agent(
    agent_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Publish agent (status: listed). Paid agents require linked Stripe account."""
    if user.role.value != "expert":
        raise HTTPException(403, "Experts only")
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Agent)
        .options(selectinload(Agent.expert).selectinload(User.expert_profile))
        .where(Agent.id == agent_id, Agent.expert_id == user.id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    if agent.price_cents > 0:
        profile = agent.expert.expert_profile if agent.expert else None
        stripe_linked = bool(profile and profile.stripe_connect_account_id)
        if not stripe_linked:
            raise HTTPException(
                400,
                "Link your Stripe account before publishing paid agents. Go to Dashboard → Settings.",
            )
    agent.status = AgentStatus.PENDING_REVIEW.value
    agent.approval_status = "pending"
    await db.commit()
    return {"status": "pending_review", "message": "Agent submitted for moderation. It will appear in the marketplace after approval."}


@router.patch("/{agent_id}/unpublish")
async def unpublish_agent(
    agent_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unpublish agent (status: draft)."""
    if user.role.value != "expert":
        raise HTTPException(403, "Experts only")
    result = await db.execute(select(Agent).where(Agent.id == agent_id, Agent.expert_id == user.id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    agent.status = AgentStatus.DRAFT.value
    agent.approval_status = "draft"
    await db.commit()
    return {"status": "draft"}
