"""Run agent endpoints - enqueue and poll."""
from uuid import uuid4

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_workspace_member
from app.core.config import settings
from app.core.workspace_permissions import can_view_outputs_only, can_view_runs
from app.core.key_encryption import decrypt_api_key
from app.db.session import get_db
from app.models.agent import Agent
from app.models.agent_run import AgentRun
from app.models.chain import AgentChain
from app.models.chain_run import ChainRun
from app.models.workspace_member import WorkspaceMember
from app.models.purchase import Purchase
from app.models.subscription import Subscription
from app.models.user import User
from app.models.user_github_token import UserGitHubToken
from app.models.user_llm_key import UserLLMKey
from app.services.manifest_validator import manifest_has_github_module

router = APIRouter(prefix="/runs", tags=["runs"])
JOB_STORE: dict[str, tuple[str, int, int | None]] = {}  # job_id -> (celery_task_id, buyer_id, run_id)

GENERIC_ERROR = "Error communicating with server. Please try again later."


def _sanitize_error(msg: str | None) -> str:
    """In production, hide internal error details."""
    if not msg:
        return GENERIC_ERROR
    if settings.ENVIRONMENT and settings.ENVIRONMENT.lower() == "production":
        return GENERIC_ERROR
    return msg


class RunRequest(BaseModel):
    agent_id: int
    user_input: str
    model: str = "openai/gpt-5.2"
    use_byok: bool = False


@router.post("/")
async def create_run(
    payload: RunRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Enqueue agent run. Returns job_id for polling. Owner (expert) or admin can run own agents even if not listed."""
    result = await db.execute(select(Agent).where(Agent.id == payload.agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    is_owner_or_admin = agent.expert_id == user.id or user.role.value == "admin"
    if not is_owner_or_admin:
        if agent.status != "listed":
            raise HTTPException(403, "Agent is not listed")
        purchase_result = await db.execute(
            select(Purchase).where(
                Purchase.buyer_id == user.id,
                Purchase.agent_id == payload.agent_id,
            )
        )
        purchase = purchase_result.scalar_one_or_none()
        if not purchase:
            raise HTTPException(403, "Purchase this agent first")
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

    github_token = None
    gh_result = await db.execute(
        select(UserGitHubToken).where(UserGitHubToken.user_id == user.id)
    )
    gh_row = gh_result.scalar_one_or_none()
    if gh_row:
        github_token = decrypt_api_key(gh_row.encrypted_token)
    if manifest_has_github_module(agent.manifest) and not github_token:
        raise HTTPException(
            400,
            "This agent uses GitHub. Add a GitHub token in settings (e.g. Users / GitHub token) first.",
        )

    from app.worker.tasks import run_agent_task

    run = AgentRun(
        user_id=user.id,
        agent_id=payload.agent_id,
        status="queued",
        user_input=payload.user_input,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    job_id = str(uuid4())
    task = run_agent_task.delay(
        agent_id=payload.agent_id,
        user_input=payload.user_input,
        model=payload.model,
        api_key=api_key,
        buyer_id=user.id if not payload.use_byok else None,
        github_token=github_token,
        run_id=run.id,
    )
    run.job_id = job_id
    await db.commit()
    JOB_STORE[job_id] = (task.id, user.id, run.id)
    return {"job_id": job_id, "run_id": run.id, "status": "queued"}


@router.get("/subscription")
async def get_subscription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's subscription and run quota."""
    result = await db.execute(select(Subscription).where(Subscription.buyer_id == user.id))
    sub = result.scalar_one_or_none()
    if not sub:
        return {"tier": "free", "runs_per_period": 5, "runs_used": 0, "runs_remaining": 5}
    return {
        "tier": sub.tier,
        "runs_per_period": sub.runs_per_period,
        "runs_used": sub.runs_used,
        "runs_remaining": max(0, sub.runs_per_period - sub.runs_used),
    }


@router.get("/history")
async def list_agent_runs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    agent_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List current user's agent runs."""
    q = select(AgentRun, Agent.name).where(AgentRun.user_id == user.id).join(
        Agent, AgentRun.agent_id == Agent.id
    )
    if agent_id is not None:
        q = q.where(AgentRun.agent_id == agent_id)
    q = q.order_by(AgentRun.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    rows = result.all()
    items = [
        {
            "id": r[0].id,
            "agent_id": r[0].agent_id,
            "agent_name": r[1],
            "status": r[0].status,
            "created_at": r[0].created_at.isoformat() if r[0].created_at else None,
        }
        for r in rows
    ]
    return {"items": items}


@router.get("/unified-history")
async def list_unified_run_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    workspace_id: int | None = Query(None),
    chain_id: int | None = Query(None),
    agent_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=200),
):
    """Unified list of chain runs and agent runs, sorted by created_at desc."""
    items: list[dict] = []

    # Chain runs (same permission logic as list_chain_runs)
    base = select(ChainRun, AgentChain.name).join(
        AgentChain, ChainRun.chain_id == AgentChain.id
    )
    if workspace_id is not None:
        member = await get_workspace_member(db, workspace_id, user.id)
        if not member:
            raise HTTPException(403, "Not a member of this workspace")
        if not (can_view_runs(member.role) or can_view_outputs_only(member.role)):
            raise HTTPException(403, "Cannot view runs in this workspace")
        base = base.where(AgentChain.workspace_id == workspace_id)
    else:
        ws_result = await db.execute(
            select(WorkspaceMember.workspace_id).where(
                WorkspaceMember.user_id == user.id,
                WorkspaceMember.role.in_(["owner", "admin", "member", "viewer"]),
            )
        )
        ws_ids = [r[0] for r in ws_result.all()]
        base = base.where(
            (ChainRun.user_id == user.id)
            | (AgentChain.workspace_id.in_(ws_ids) if ws_ids else (AgentChain.id < 0))
        )
    if chain_id is not None:
        base = base.where(ChainRun.chain_id == chain_id)
    base = base.order_by(ChainRun.created_at.desc())
    chain_result = await db.execute(base)
    for run, chain_name in chain_result.all():
        items.append({
            "source": "chain",
            "run_id": run.id,
            "label": chain_name or f"Chain #{run.chain_id}",
            "chain_id": run.chain_id,
            "agent_id": None,
            "status": run.status,
            "created_at": run.created_at.isoformat() if run.created_at else None,
        })

    # Agent runs
    agent_q = select(AgentRun, Agent.name).where(AgentRun.user_id == user.id).join(
        Agent, AgentRun.agent_id == Agent.id
    )
    if agent_id is not None:
        agent_q = agent_q.where(AgentRun.agent_id == agent_id)
    agent_q = agent_q.order_by(AgentRun.created_at.desc())
    agent_result = await db.execute(agent_q)
    for run, agent_name in agent_result.all():
        items.append({
            "source": "agent",
            "run_id": run.id,
            "label": agent_name or f"Agent #{run.agent_id}",
            "chain_id": None,
            "agent_id": run.agent_id,
            "status": run.status,
            "created_at": run.created_at.isoformat() if run.created_at else None,
        })

    # Sort by created_at desc and limit
    items.sort(key=lambda x: x["created_at"] or "", reverse=True)
    items = items[:limit]
    return {"items": items}


@router.get("/agent-runs/{run_id}")
async def get_agent_run_result(
    run_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single agent run by id."""
    result = await db.execute(
        select(AgentRun, Agent.name).where(
            AgentRun.id == run_id,
        ).join(Agent, AgentRun.agent_id == Agent.id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(404, "Run not found")
    run, agent_name = row[0], row[1]
    if run.user_id != user.id:
        raise HTTPException(404, "Run not found")
    return {
        "id": run.id,
        "agent_id": run.agent_id,
        "agent_name": agent_name,
        "status": run.status,
        "user_input": run.user_input,
        "content": run.content,
        "error": run.error,
        "usage": run.usage,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


@router.get("/{job_id}")
async def get_run_status(
    job_id: str,
    user: User = Depends(get_current_user),
):
    """Poll run status and result."""
    from app.worker.celery_app import celery_app

    stored = JOB_STORE.get(job_id)
    if not stored:
        raise HTTPException(404, "Job not found")
    task_id = stored[0]
    stored_user_id = stored[1] if len(stored) > 1 else None
    run_id = stored[2] if len(stored) > 2 else None
    if stored_user_id is not None and stored_user_id != user.id:
        raise HTTPException(404, "Job not found")
    result = AsyncResult(task_id, app=celery_app)
    if result.state == "PENDING":
        out = {"job_id": job_id, "status": "pending"}
        if run_id is not None:
            out["run_id"] = run_id
        return out
    if result.state == "SUCCESS":
        data = result.result or {}
        if data.get("status") == "error":
            out = {"job_id": job_id, "status": "error", "error": _sanitize_error(data.get("error"))}
            if run_id is not None:
                out["run_id"] = run_id
            return out
        content = data.get("content")
        # Content may contain error message from sandbox (Docker error, etc.)
        if content and any(
            x in (content or "")
            for x in ("Docker error", "Sandbox image", "Execution error", "No response file", "Error:")
        ):
            content = _sanitize_error(content) if content else content
        out = {"job_id": job_id, "status": "completed", "content": content, "usage": data.get("usage")}
        if run_id is not None:
            out["run_id"] = run_id
        return out
    if result.state == "FAILURE":
        out = {"job_id": job_id, "status": "error", "error": _sanitize_error(str(result.result))}
        if run_id is not None:
            out["run_id"] = run_id
        return out
    out = {"job_id": job_id, "status": result.state.lower()}
    if run_id is not None:
        out["run_id"] = run_id
    return out
