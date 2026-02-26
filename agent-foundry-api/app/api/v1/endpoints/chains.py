"""Chain endpoints - CRUD, compatibility, run."""
from uuid import uuid4

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.key_encryption import decrypt_api_key
from app.db.session import get_db
from app.models.agent import Agent
from app.models.chain import AgentChain
from app.models.purchase import Purchase
from app.models.subscription import Subscription
from app.models.user import User
from app.models.user_llm_key import UserLLMKey
from app.schemas.chain import (
    ChainCreate,
    ChainRunRequest,
    ChainUpdate,
)
from app.services.chain_compatibility import can_chain, validate_chain_definition
from app.worker.celery_app import celery_app
from app.worker.tasks import run_chain_task

router = APIRouter(prefix="/chains", tags=["chains"])
CHAIN_JOB_STORE: dict[str, tuple[str, int]] = {}  # job_id -> (celery_task_id, buyer_id)

GENERIC_ERROR = "Error communicating with server. Please try again later."


def _sanitize_error(msg: str | None) -> str:
    if not msg:
        return GENERIC_ERROR
    if settings.ENVIRONMENT and settings.ENVIRONMENT.lower() == "production":
        return GENERIC_ERROR
    return msg


async def _agent_lookup_from_ids(db: AsyncSession, agent_ids: list[int], buyer_id: int) -> dict[int, Agent]:
    """Load agents and filter to those purchased by buyer."""
    if not agent_ids:
        return {}
    result = await db.execute(
        select(Agent, Purchase)
        .join(Purchase, (Purchase.agent_id == Agent.id) & (Purchase.buyer_id == buyer_id))
        .where(Agent.id.in_(agent_ids), Agent.status == "listed")
    )
    return {row[0].id: row[0] for row in result.all()}


@router.post("")
async def create_chain(
    payload: ChainCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a chain. Validates agents purchased and edge compatibility."""
    defn = payload.definition
    nodes = defn.get("nodes", [])
    edges = defn.get("edges", [])

    agent_ids = list({n.get("agent_id") for n in nodes if n.get("agent_id") is not None})
    agent_lookup = await _agent_lookup_from_ids(db, agent_ids, user.id)

    errors = validate_chain_definition(nodes, edges, agent_lookup)
    if errors:
        raise HTTPException(400, detail={"message": "Invalid chain", "errors": errors})

    chain = AgentChain(buyer_id=user.id, name=payload.name, definition=defn)
    db.add(chain)
    await db.commit()
    await db.refresh(chain)
    return {
        "id": chain.id,
        "name": chain.name,
        "definition": chain.definition,
        "created_at": chain.created_at.isoformat() if chain.created_at else None,
        "updated_at": chain.updated_at.isoformat() if chain.updated_at else None,
    }


@router.get("")
async def list_chains(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List current user's chains."""
    result = await db.execute(
        select(AgentChain).where(AgentChain.buyer_id == user.id).order_by(AgentChain.updated_at.desc())
    )
    chains = result.scalars().all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "definition": c.definition,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in chains
    ]


@router.get("/compatibility")
async def check_compatibility(
    agent_a: int = Query(..., description="Source agent ID"),
    agent_b: int = Query(..., description="Target agent ID"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check if agent A's output can feed agent B's input."""
    agent_lookup = await _agent_lookup_from_ids(db, [agent_a, agent_b], user.id)
    a = agent_lookup.get(agent_a)
    b = agent_lookup.get(agent_b)
    if not a:
        raise HTTPException(404, "Agent A not found or not purchased")
    if not b:
        raise HTTPException(404, "Agent B not found or not purchased")
    return {"compatible": can_chain(a, b)}


@router.get("/runs/{job_id}")
async def get_chain_run_status(job_id: str):
    """Poll chain run status and result."""
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


@router.get("/{chain_id}")
async def get_chain(
    chain_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get chain with agent details."""
    result = await db.execute(
        select(AgentChain).where(AgentChain.id == chain_id, AgentChain.buyer_id == user.id)
    )
    chain = result.scalar_one_or_none()
    if not chain:
        raise HTTPException(404, "Chain not found")

    agent_ids = list({n.get("agent_id") for n in chain.definition.get("nodes", []) if n.get("agent_id") is not None})
    agents_result = await db.execute(
        select(Agent).where(Agent.id.in_(agent_ids)) if agent_ids else select(Agent).limit(0)
    )
    agents = {a.id: {"id": a.id, "name": a.name, "description": a.description} for a in agents_result.scalars().all()}

    return {
        "id": chain.id,
        "name": chain.name,
        "definition": chain.definition,
        "created_at": chain.created_at.isoformat() if chain.created_at else None,
        "updated_at": chain.updated_at.isoformat() if chain.updated_at else None,
        "agents": [agents.get(aid, {"id": aid, "name": "?", "description": None}) for aid in agent_ids],
    }


@router.put("/{chain_id}")
async def update_chain(
    chain_id: int,
    payload: ChainUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update chain."""
    result = await db.execute(
        select(AgentChain).where(AgentChain.id == chain_id, AgentChain.buyer_id == user.id)
    )
    chain = result.scalar_one_or_none()
    if not chain:
        raise HTTPException(404, "Chain not found")

    if payload.definition is not None:
        defn = payload.definition
        nodes = defn.get("nodes", [])
        edges = defn.get("edges", [])
        agent_ids = list({n.get("agent_id") for n in nodes if n.get("agent_id") is not None})
        agent_lookup = await _agent_lookup_from_ids(db, agent_ids, user.id)
        errors = validate_chain_definition(nodes, edges, agent_lookup)
        if errors:
            raise HTTPException(400, detail={"message": "Invalid chain", "errors": errors})
        chain.definition = defn

    if payload.name is not None:
        chain.name = payload.name

    await db.commit()
    await db.refresh(chain)
    return {
        "id": chain.id,
        "name": chain.name,
        "definition": chain.definition,
        "created_at": chain.created_at.isoformat() if chain.created_at else None,
        "updated_at": chain.updated_at.isoformat() if chain.updated_at else None,
    }


@router.post("/{chain_id}/run")
async def run_chain(
    chain_id: int,
    payload: ChainRunRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute chain. Returns job_id for polling."""
    result = await db.execute(
        select(AgentChain).where(AgentChain.id == chain_id, AgentChain.buyer_id == user.id)
    )
    chain = result.scalar_one_or_none()
    if not chain:
        raise HTTPException(404, "Chain not found")

    if not payload.use_byok:
        sub_result = await db.execute(
            select(Subscription).where(Subscription.buyer_id == user.id)
        )
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

    job_id = str(uuid4())
    task = run_chain_task.delay(
        chain_id=chain_id,
        user_input=payload.user_input,
        model=payload.model,
        api_key=api_key,
        buyer_id=user.id if not payload.use_byok else None,
    )
    CHAIN_JOB_STORE[job_id] = (task.id, user.id)
    return {"job_id": job_id, "status": "queued"}
