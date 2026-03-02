"""Chain endpoints - marketplace, moderation lifecycle, and run."""
from uuid import uuid4

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_optional
from app.core.config import settings
from app.core.key_encryption import decrypt_api_key
from app.db.session import get_db
from app.models.agent import Agent, AgentStatus
from app.models.chain import AgentChain, ChainStatus
from app.models.purchase import Purchase
from app.models.subscription import Subscription
from app.models.user import User
from app.models.user_github_token import UserGitHubToken
from app.models.user_llm_key import UserLLMKey
from app.models.user_personality import UserPersonalityProfile
from app.schemas.chain import ChainCreate, ChainListResponse, ChainResponse, ChainRunRequest, ChainUpdate
from app.services.chain_compatibility import can_chain, validate_chain_definition
from app.services.manifest_validator import manifest_has_github_module

router = APIRouter(prefix="/chains", tags=["chains"])
CHAIN_JOB_STORE: dict[str, tuple[str, int]] = {}  # job_id -> (celery_task_id, buyer_id)

GENERIC_ERROR = "Error communicating with server. Please try again later."


def _sanitize_error(msg: str | None) -> str:
    if not msg:
        return GENERIC_ERROR
    if settings.ENVIRONMENT and settings.ENVIRONMENT.lower() == "production":
        return GENERIC_ERROR
    return msg


async def _agent_lookup_for_chain_definition(db: AsyncSession, agent_ids: list[int]) -> dict[int, Agent]:
    """Load agents that may be included in marketplace chains (listed + approved only)."""
    if not agent_ids:
        return {}
    result = await db.execute(
        select(Agent).where(
            Agent.id.in_(agent_ids),
            Agent.status == AgentStatus.LISTED.value,
            Agent.approval_status == "approved",
        )
    )
    agents = result.scalars().all()
    return {a.id: a for a in agents}


async def _agent_lookup_for_chain_definition_with_own(
    db: AsyncSession, agent_ids: list[int], user_id: int
) -> dict[int, Agent]:
    """Load agents for save/update: listed+approved OR owned by user (so own unpublished agents are allowed)."""
    if not agent_ids:
        return {}
    result = await db.execute(
        select(Agent).where(
            Agent.id.in_(agent_ids),
            or_(
                (Agent.status == AgentStatus.LISTED.value) & (Agent.approval_status == "approved"),
                Agent.expert_id == user_id,
            ),
        )
    )
    agents = result.scalars().all()
    return {a.id: a for a in agents}


async def _has_chain_run_access(db: AsyncSession, chain: AgentChain, user: User) -> bool:
    """A user can run a chain if owner/expert/admin/mod, purchased chain, or purchased all included agents."""
    if user.role.value in ("admin", "moderator"):
        return True
    if chain.expert_id == user.id or chain.buyer_id == user.id:
        return True

    chain_purchase = await db.execute(
        select(Purchase).where(Purchase.buyer_id == user.id, Purchase.chain_id == chain.id)
    )
    if chain_purchase.scalar_one_or_none():
        return True

    agent_ids = list(
        {n.get("agent_id") for n in (chain.definition or {}).get("nodes", []) if n.get("agent_id") is not None}
    )
    if not agent_ids:
        return False
    result = await db.execute(
        select(Purchase.agent_id).where(
            Purchase.buyer_id == user.id,
            Purchase.agent_id.in_(agent_ids),
        )
    )
    purchased_agent_ids = {row[0] for row in result.all() if row[0] is not None}
    return set(agent_ids).issubset(purchased_agent_ids)


def _chain_to_dict(chain: AgentChain) -> dict:
    return {
        "id": chain.id,
        "name": chain.name,
        "description": chain.description,
        "price_cents": chain.price_cents,
        "status": chain.status,
        "approval_status": chain.approval_status,
        "category": chain.category,
        "tags": chain.tags or [],
        "definition": chain.definition,
        "rejection_reason": chain.rejection_reason,
        "created_at": chain.created_at.isoformat() if chain.created_at else None,
        "updated_at": chain.updated_at.isoformat() if chain.updated_at else None,
    }


@router.get("/marketplace", response_model=list[ChainListResponse])
async def list_marketplace_chains(
    db: AsyncSession = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
    category: str | None = None,
):
    """List public chains (listed + approved only)."""
    q = select(AgentChain).where(
        AgentChain.status == ChainStatus.LISTED.value,
        AgentChain.approval_status == "approved",
    )
    if category:
        q = q.where(AgentChain.category == category)
    q = q.order_by(AgentChain.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    chains = result.scalars().all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "price_cents": c.price_cents,
            "status": c.status,
            "approval_status": c.approval_status,
            "category": c.category,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in chains
    ]


@router.get("/my", response_model=list[ChainListResponse])
async def list_my_chains(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List current expert's authored chains."""
    if user.role.value not in ("expert", "admin"):
        raise HTTPException(403, "Expert or admin access required")
    result = await db.execute(
        select(AgentChain)
        .where(AgentChain.expert_id == user.id)
        .order_by(AgentChain.updated_at.desc())
    )
    chains = result.scalars().all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "price_cents": c.price_cents,
            "status": c.status,
            "approval_status": c.approval_status,
            "category": c.category,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in chains
    ]


@router.post("", response_model=ChainResponse)
async def create_chain(
    payload: ChainCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a chain listing draft (experts only)."""
    if user.role.value not in ("expert", "admin"):
        raise HTTPException(403, "Expert or admin access required")

    defn = payload.definition
    nodes = defn.get("nodes", [])
    edges = defn.get("edges", [])
    agent_ids = list({n.get("agent_id") for n in nodes if n.get("agent_id") is not None})
    agent_lookup = await _agent_lookup_for_chain_definition_with_own(db, agent_ids, user.id)
    errors = validate_chain_definition(nodes, edges, agent_lookup)
    if errors:
        raise HTTPException(400, detail={"message": "Invalid chain", "errors": errors})

    chain = AgentChain(
        buyer_id=user.id,
        expert_id=user.id,
        name=payload.name,
        description=payload.description,
        definition=defn,
        price_cents=payload.price_cents,
        status=ChainStatus.DRAFT.value,
        category=payload.category,
        tags=payload.tags,
        approval_status="draft",
    )
    db.add(chain)
    await db.commit()
    await db.refresh(chain)
    return _chain_to_dict(chain)


@router.get("/compatibility")
async def check_compatibility(
    agent_a: int = Query(..., description="Source agent ID"),
    agent_b: int = Query(..., description="Target agent ID"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check if agent A's output can feed agent B's input (includes your own unpublished agents)."""
    if user.role.value not in ("expert", "admin"):
        raise HTTPException(403, "Expert or admin access required")
    agent_lookup = await _agent_lookup_for_chain_definition_with_own(db, [agent_a, agent_b], user.id)
    a = agent_lookup.get(agent_a)
    b = agent_lookup.get(agent_b)
    if not a:
        raise HTTPException(404, "Agent A not found or not accessible")
    if not b:
        raise HTTPException(404, "Agent B not found or not accessible")
    return {"compatible": can_chain(a, b)}


@router.get("/runs/{job_id}")
async def get_chain_run_status(job_id: str):
    """Poll chain run status and result."""
    from app.worker.celery_app import celery_app

    stored = CHAIN_JOB_STORE.get(job_id)
    task_id = stored[0] if isinstance(stored, tuple) else stored
    if not task_id:
        raise HTTPException(404, "Job not found")
    result = AsyncResult(task_id, app=celery_app)
    if result.state == "PENDING":
        return {"job_id": job_id, "status": "pending"}
    if result.state == "SUCCESS":
        data = result.result or {}
        content = data.get("content")
        if content and any(
            x in (content or "")
            for x in ("Docker error", "Sandbox image", "Execution error", "No response file", "Error:")
        ):
            content = _sanitize_error(content) if content else content
        return {"job_id": job_id, "status": "completed", "content": content, "usage": data.get("usage")}
    if result.state == "FAILURE":
        return {"job_id": job_id, "status": "error", "error": _sanitize_error(str(result.result))}
    return {"job_id": job_id, "status": result.state.lower()}


@router.get("/{chain_id}", response_model=ChainResponse)
async def get_chain(
    chain_id: int,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Get chain details (public for listed+approved; full for owner/admin/mod)."""
    result = await db.execute(select(AgentChain).where(AgentChain.id == chain_id))
    chain = result.scalar_one_or_none()
    if not chain:
        raise HTTPException(404, "Chain not found")

    is_public = (
        chain.status == ChainStatus.LISTED.value
        and chain.approval_status == "approved"
    )
    is_owner_or_staff = bool(
        user
        and (
            user.id in (chain.expert_id, chain.buyer_id)
            or user.role.value in ("admin", "moderator")
        )
    )
    if not is_public and not is_owner_or_staff:
        raise HTTPException(404, "Chain not found")

    agent_ids = list(
        {n.get("agent_id") for n in (chain.definition or {}).get("nodes", []) if n.get("agent_id") is not None}
    )
    agents_result = await db.execute(
        select(Agent).where(Agent.id.in_(agent_ids)) if agent_ids else select(Agent).limit(0)
    )
    agents = {
        a.id: {"id": a.id, "name": a.name, "description": a.description, "expert_id": a.expert_id}
        for a in agents_result.scalars().all()
    }
    out = _chain_to_dict(chain)
    out["agents"] = [agents.get(aid, {"id": aid, "name": "?", "description": None}) for aid in agent_ids]
    return out


@router.put("/{chain_id}", response_model=ChainResponse)
async def update_chain(
    chain_id: int,
    payload: ChainUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update authored chain draft/rejected chain."""
    if user.role.value not in ("expert", "admin"):
        raise HTTPException(403, "Expert or admin access required")
    result = await db.execute(
        select(AgentChain).where(AgentChain.id == chain_id, AgentChain.expert_id == user.id)
    )
    chain = result.scalar_one_or_none()
    if not chain:
        raise HTTPException(404, "Chain not found")

    if payload.definition is not None:
        defn = payload.definition
        nodes = defn.get("nodes", [])
        edges = defn.get("edges", [])
        agent_ids = list({n.get("agent_id") for n in nodes if n.get("agent_id") is not None})
        agent_lookup = await _agent_lookup_for_chain_definition_with_own(db, agent_ids, user.id)
        errors = validate_chain_definition(nodes, edges, agent_lookup)
        if errors:
            raise HTTPException(400, detail={"message": "Invalid chain", "errors": errors})
        chain.definition = defn

    if payload.name is not None:
        chain.name = payload.name
    if payload.description is not None:
        chain.description = payload.description
    if payload.price_cents is not None:
        chain.price_cents = payload.price_cents
    if payload.category is not None:
        chain.category = payload.category
    if payload.tags is not None:
        chain.tags = payload.tags

    if chain.status == ChainStatus.REJECTED.value:
        chain.approval_status = "draft"

    await db.commit()
    await db.refresh(chain)
    return _chain_to_dict(chain)


@router.patch("/{chain_id}/publish")
async def publish_chain(
    chain_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit chain for moderation review. All agents in the chain must be published (listed) first."""
    if user.role.value not in ("expert", "admin"):
        raise HTTPException(403, "Expert or admin access required")
    result = await db.execute(
        select(AgentChain).where(AgentChain.id == chain_id, AgentChain.expert_id == user.id)
    )
    chain = result.scalar_one_or_none()
    if not chain:
        raise HTTPException(404, "Chain not found")
    agent_ids = list(
        {n.get("agent_id") for n in (chain.definition or {}).get("nodes", []) if n.get("agent_id") is not None}
    )
    if agent_ids:
        agents_result = await db.execute(
            select(Agent).where(Agent.id.in_(agent_ids))
        )
        agents = agents_result.scalars().all()
        unpublished = [
            a.name or f"Agent #{a.id}"
            for a in agents
            if a.status != AgentStatus.LISTED.value or a.approval_status != "approved"
        ]
        if unpublished:
            raise HTTPException(
                400,
                f"All agents in the chain must be published before you can publish the chain. Unpublished: {', '.join(unpublished)}",
            )
    if chain.price_cents > 0:
        profile_result = await db.execute(
            select(User).options(selectinload(User.expert_profile)).where(User.id == user.id)
        )
        profile_user = profile_result.scalar_one_or_none()
        profile = profile_user.expert_profile if profile_user else None
        if not profile or not profile.stripe_connect_account_id:
            raise HTTPException(
                400,
                "Link your Stripe account before publishing paid chains. Go to Dashboard -> Settings.",
            )
    chain.status = ChainStatus.PENDING_REVIEW.value
    chain.approval_status = "pending"
    await db.commit()
    return {"status": "pending_review", "message": "Chain submitted for moderation."}


@router.patch("/{chain_id}/unpublish")
async def unpublish_chain(
    chain_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Move chain back to draft."""
    if user.role.value not in ("expert", "admin"):
        raise HTTPException(403, "Expert or admin access required")
    result = await db.execute(
        select(AgentChain).where(AgentChain.id == chain_id, AgentChain.expert_id == user.id)
    )
    chain = result.scalar_one_or_none()
    if not chain:
        raise HTTPException(404, "Chain not found")
    chain.status = ChainStatus.DRAFT.value
    chain.approval_status = "draft"
    await db.commit()
    return {"status": "draft"}


@router.post("/{chain_id}/run")
async def run_chain(
    chain_id: int,
    payload: ChainRunRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute chain. Returns job_id for polling."""
    result = await db.execute(select(AgentChain).where(AgentChain.id == chain_id))
    chain = result.scalar_one_or_none()
    if not chain:
        raise HTTPException(404, "Chain not found")
    if not await _has_chain_run_access(db, chain, user):
        raise HTTPException(403, "Purchase this chain or required agents first")

    if not payload.use_byok:
        sub_result = await db.execute(select(Subscription).where(Subscription.buyer_id == user.id))
        sub = sub_result.scalar_one_or_none()
        if sub and sub.runs_used >= sub.runs_per_period:
            raise HTTPException(
                429,
                f"Run limit reached ({sub.runs_used}/{sub.runs_per_period} this period). Use BYOK or upgrade.",
            )

    api_key = None
    if payload.use_byok:
        provider = payload.model.split("/")[0] if "/" in payload.model else "openai"
        key_result = await db.execute(
            select(UserLLMKey).where(
                UserLLMKey.user_id == user.id,
                UserLLMKey.provider == provider,
            )
        )
        row = key_result.scalar_one_or_none()
        if row:
            api_key = decrypt_api_key(row.encrypted_key)
        else:
            raise HTTPException(400, f"No BYOK key for {provider}")

    personality_text = None
    profile_result = await db.execute(
        select(UserPersonalityProfile).where(UserPersonalityProfile.user_id == user.id)
    )
    profile = profile_result.scalar_one_or_none()
    if profile and (profile.profile_text or "").strip():
        personality_text = profile.profile_text.strip()

    github_token = None
    defn = chain.definition or {}
    agent_ids = {n.get("agent_id") for n in defn.get("nodes", []) if n.get("agent_id") is not None}
    if agent_ids:
        agents_result = await db.execute(select(Agent).where(Agent.id.in_(agent_ids)))
        agents_list = agents_result.scalars().all()
        if any(manifest_has_github_module(a.manifest or {}) for a in agents_list):
            gh_result = await db.execute(
                select(UserGitHubToken).where(UserGitHubToken.user_id == user.id)
            )
            gh_row = gh_result.scalar_one_or_none()
            if not gh_row:
                raise HTTPException(
                    400,
                    "This chain uses GitHub. Add a GitHub token in settings (e.g. Users / GitHub token) first.",
                )
            github_token = decrypt_api_key(gh_row.encrypted_token)

    from app.worker.tasks import run_chain_task

    job_id = str(uuid4())
    task = run_chain_task.delay(
        chain_id=chain_id,
        user_input=payload.user_input,
        model=payload.model,
        api_key=api_key,
        buyer_id=user.id if not payload.use_byok else None,
        personality_text=personality_text,
        run_type=payload.run_type,
        run_owner_id=user.id,
        github_token=github_token,
    )
    CHAIN_JOB_STORE[job_id] = (task.id, user.id)
    return {"job_id": job_id, "status": "queued"}
