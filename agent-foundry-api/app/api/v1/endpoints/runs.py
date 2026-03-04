"""Run agent endpoints - enqueue and poll."""
from uuid import uuid4

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.key_encryption import decrypt_api_key
from app.db.session import get_db
from app.models.agent import Agent
from app.models.purchase import Purchase
from app.models.subscription import Subscription
from app.models.user import User
from app.models.user_github_token import UserGitHubToken
from app.models.user_llm_key import UserLLMKey
from app.services.manifest_validator import manifest_has_github_module

router = APIRouter(prefix="/runs", tags=["runs"])
JOB_STORE: dict[str, tuple[str, int]] = {}  # job_id -> (celery_task_id, buyer_id)

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

    job_id = str(uuid4())
    task = run_agent_task.delay(
        agent_id=payload.agent_id,
        user_input=payload.user_input,
        model=payload.model,
        api_key=api_key,
        buyer_id=user.id if not payload.use_byok else None,
        github_token=github_token,
    )
    JOB_STORE[job_id] = (task.id, user.id)
    return {"job_id": job_id, "status": "queued"}


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


@router.get("/{job_id}")
async def get_run_status(job_id: str):
    """Poll run status and result."""
    from app.worker.celery_app import celery_app

    stored = JOB_STORE.get(job_id)
    task_id = stored[0] if isinstance(stored, tuple) else stored
    if not task_id:
        raise HTTPException(404, "Job not found")
    result = AsyncResult(task_id, app=celery_app)
    if result.state == "PENDING":
        return {"job_id": job_id, "status": "pending"}
    if result.state == "SUCCESS":
        data = result.result or {}
        content = data.get("content")
        # Content may contain error message from sandbox (Docker error, etc.)
        if content and any(
            x in (content or "")
            for x in ("Docker error", "Sandbox image", "Execution error", "No response file", "Error:")
        ):
            content = _sanitize_error(content) if content else content
        return {"job_id": job_id, "status": "completed", "content": content, "usage": data.get("usage")}
    if result.state == "FAILURE":
        return {"job_id": job_id, "status": "error", "error": _sanitize_error(str(result.result))}
    return {"job_id": job_id, "status": result.state.lower()}
