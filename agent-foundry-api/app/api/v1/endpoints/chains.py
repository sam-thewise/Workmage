"""Chain endpoints - marketplace, moderation lifecycle, and run."""
import secrets
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_current_user_optional,
    get_workspace_member,
    require_workspace_role,
)
from app.core.config import settings
from app.core.workspace_permissions import (
    can_edit_teams,
    can_run_teams,
    can_view_runs,
    can_view_outputs_only,
)
from app.core.key_encryption import decrypt_api_key
from app.db.session import get_db
from app.models.agent import Agent, AgentStatus
from app.models.chain import AgentChain, ChainStatus
from app.models.chain_approval import ChainApprovalRequest
from app.models.agent_run import AgentRun
from app.models.chain_run import ChainRun
from app.models.purchase import Purchase
from app.models.run_share_link import RunShareLink
from app.models.workspace_member import WorkspaceMember
from app.models.subscription import Subscription
from app.models.user import User
from app.models.user_github_token import UserGitHubToken
from app.models.user_llm_key import UserLLMKey
from app.models.user_personality import UserPersonalityProfile
from app.schemas.chain import ChainCreate, ChainListResponse, ChainResponse, ChainRunRequest, ChainUpdate
from app.services.chain_compatibility import can_chain, validate_chain_definition
from app.services.manifest_validator import manifest_has_github_module

router = APIRouter(prefix="/chains", tags=["chains"])
CHAIN_JOB_STORE: dict[str, tuple[str, int, int | None]] = {}  # job_id -> (celery_task_id, user_id, run_id | None)

GENERIC_ERROR = "Error communicating with server. Please try again later."


class ChainApprovalApproveRequest(BaseModel):
    approved: bool = True
    next_stage_node_id: str | None = None


class RunShareCreate(BaseModel):
    expires_in_seconds: int | None = None


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
    """A user can run a chain if workspace member with run permission, owner/expert/admin/mod, purchased chain, or purchased all included agents."""
    if user.role.value in ("admin", "moderator"):
        return True
    if chain.workspace_id is not None:
        member = await get_workspace_member(db, chain.workspace_id, user.id)
        if member and can_run_teams(member.role):
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
        "workspace_id": chain.workspace_id,
        "name": chain.name,
        "description": chain.description,
        "price_cents": chain.price_cents,
        "status": chain.status,
        "approval_status": chain.approval_status,
        "category": chain.category,
        "slug": getattr(chain, "slug", None),
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
            "slug": getattr(c, "slug", None),
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in chains
    ]


@router.get("/runnable", response_model=list[ChainListResponse])
async def list_runnable_chains(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List chains the user can run (own, workspace, or purchased). For Create report / comparison flow."""
    chain_ids = set()
    q = select(AgentChain.id).where(
        (AgentChain.expert_id == user.id) | (AgentChain.buyer_id == user.id)
    )
    for row in (await db.execute(q)).all():
        chain_ids.add(row[0])
    ws_run = await db.execute(
        select(WorkspaceMember.workspace_id).where(
            WorkspaceMember.user_id == user.id,
            WorkspaceMember.role.in_(["owner", "admin", "member"]),
        )
    )
    ws_ids = [r[0] for r in ws_run.all()]
    if ws_ids:
        q2 = select(AgentChain.id).where(AgentChain.workspace_id.in_(ws_ids))
        for row in (await db.execute(q2)).all():
            chain_ids.add(row[0])
    purch = await db.execute(
        select(Purchase.chain_id).where(
            Purchase.buyer_id == user.id,
            Purchase.chain_id.isnot(None),
        )
    )
    for row in purch.all():
        if row[0]:
            chain_ids.add(row[0])
    if not chain_ids:
        return []
    result = await db.execute(
        select(AgentChain).where(AgentChain.id.in_(chain_ids)).order_by(AgentChain.updated_at.desc())
    )
    all_chains = result.scalars().all()
    chains = [c for c in all_chains if await _has_chain_run_access(db, c, user)]
    return [
        {
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "price_cents": c.price_cents,
            "status": c.status,
            "approval_status": c.approval_status,
            "category": c.category,
            "slug": getattr(c, "slug", None),
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in chains
    ]


@router.get("/my", response_model=list[ChainListResponse])
async def list_my_chains(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    workspace_id: int | None = Query(None),
):
    """List chains user can edit: own authored or workspace chains (with can_edit_teams)."""
    if user.role.value not in ("expert", "admin"):
        raise HTTPException(403, "Expert or admin access required")
    if workspace_id is not None:
        member = await get_workspace_member(db, workspace_id, user.id)
        if not member or not can_edit_teams(member.role):
            raise HTTPException(403, "Not a member or cannot edit chains in this workspace")
        q = select(AgentChain).where(AgentChain.workspace_id == workspace_id)
    else:
        ws_ids_result = await db.execute(
            select(WorkspaceMember.workspace_id).where(
                WorkspaceMember.user_id == user.id,
                WorkspaceMember.role.in_(["owner", "admin", "member"]),
            )
        )
        ws_id_list = [r[0] for r in ws_ids_result.all()]
        q = select(AgentChain).where(
            (AgentChain.expert_id == user.id)
            | (AgentChain.workspace_id.in_(ws_id_list) if ws_id_list else AgentChain.id < 0)
        )
    q = q.order_by(AgentChain.updated_at.desc())
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
            "slug": getattr(c, "slug", None),
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
    """Create a chain listing draft (experts only). Optionally scoped to workspace."""
    if user.role.value not in ("expert", "admin"):
        raise HTTPException(403, "Expert or admin access required")

    workspace_id = payload.workspace_id
    if workspace_id is not None:
        member = await get_workspace_member(db, workspace_id, user.id)
        if not member or not can_edit_teams(member.role):
            raise HTTPException(403, "Not allowed to create chains in this workspace")
    else:
        # Default to user's first workspace (owner) if any
        first_ws = await db.execute(
            select(WorkspaceMember.workspace_id).where(
                WorkspaceMember.user_id == user.id,
                WorkspaceMember.role == "owner",
            ).limit(1)
        )
        row = first_ws.first()
        if row:
            workspace_id = row[0]

    defn = payload.definition
    nodes = defn.get("nodes", [])
    edges = defn.get("edges", [])
    agent_ids = list({n.get("agent_id") for n in nodes if n.get("agent_id") is not None})
    agent_lookup = await _agent_lookup_for_chain_definition_with_own(db, agent_ids, user.id)
    errors = validate_chain_definition(nodes, edges, agent_lookup)
    if errors:
        raise HTTPException(400, detail={"message": "Invalid chain", "errors": errors})

    chain = AgentChain(
        workspace_id=workspace_id,
        buyer_id=user.id,
        expert_id=user.id,
        name=payload.name,
        description=payload.description,
        definition=defn,
        price_cents=payload.price_cents,
        status=ChainStatus.DRAFT.value,
        category=payload.category,
        tags=payload.tags,
        slug=payload.slug or None,
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


@router.get("/runs")
async def list_chain_runs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    chain_id: int | None = Query(None),
    workspace_id: int | None = Query(None),
    status: str | None = Query(None),
    unread_only: bool = Query(False),
):
    """List chain runs: own runs or runs in workspaces where user has view permission."""
    base = select(ChainRun, AgentChain.name).join(
        AgentChain, ChainRun.chain_id == AgentChain.id
    )
    ws_id_list: list[int] = []
    if workspace_id is not None:
        member = await get_workspace_member(db, workspace_id, user.id)
        if not member:
            raise HTTPException(403, "Not a member of this workspace")
        if not (can_view_runs(member.role) or can_view_outputs_only(member.role)):
            raise HTTPException(403, "Cannot view runs in this workspace")
        q = base.where(AgentChain.workspace_id == workspace_id)
    else:
        ws_ids_result = await db.execute(
            select(WorkspaceMember.workspace_id).where(
                WorkspaceMember.user_id == user.id,
                WorkspaceMember.role.in_(["owner", "admin", "member", "viewer"]),
            )
        )
        ws_id_list = [r[0] for r in ws_ids_result.all()]
        q = base.where(
            (ChainRun.user_id == user.id)
            | (AgentChain.workspace_id.in_(ws_id_list) if ws_id_list else AgentChain.id < 0)
        )
    if chain_id is not None:
        q = q.where(ChainRun.chain_id == chain_id)
    if status:
        q = q.where(ChainRun.status == status)
    if unread_only:
        q = q.where(ChainRun.read_at.is_(None))
    q = q.order_by(ChainRun.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    rows = result.all()
    count_q = select(func.count(ChainRun.id)).join(AgentChain, ChainRun.chain_id == AgentChain.id).where(
        ChainRun.read_at.is_(None)
    )
    if workspace_id is not None:
        count_q = count_q.where(AgentChain.workspace_id == workspace_id)
    else:
        count_q = count_q.where(
            (ChainRun.user_id == user.id)
            | (AgentChain.workspace_id.in_(ws_id_list) if ws_id_list else AgentChain.id < 0)
        )
    if chain_id is not None:
        count_q = count_q.where(ChainRun.chain_id == chain_id)
    if status:
        count_q = count_q.where(ChainRun.status == status)
    unread_total = (await db.execute(count_q)).scalar() or 0
    items = [
        {
            "id": r[0].id,
            "chain_id": r[0].chain_id,
            "chain_name": r[1],
            "status": r[0].status,
            "created_at": r[0].created_at.isoformat() if r[0].created_at else None,
            "read_at": r[0].read_at.isoformat() if r[0].read_at else None,
            "approval_id": r[0].approval_id,
        }
        for r in rows
    ]
    return {"items": items, "unread_count": unread_total}


@router.get("/runs/result/{run_id}")
async def get_chain_run_result(
    run_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single run by id. Viewer role sees only content/summary (output only)."""
    result = await db.execute(
        select(ChainRun, AgentChain.name, AgentChain.workspace_id).where(
            ChainRun.id == run_id,
        ).join(AgentChain, ChainRun.chain_id == AgentChain.id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(404, "Run not found")
    run, chain_name, chain_workspace_id = row[0], row[1], row[2]
    is_owner = run.user_id == user.id
    member = await get_workspace_member(db, chain_workspace_id, user.id) if chain_workspace_id else None
    can_view = is_owner or (member and (can_view_runs(member.role) or can_view_outputs_only(member.role)))
    if not can_view:
        raise HTTPException(404, "Run not found")
    viewer_only = member and can_view_outputs_only(member.role) and not is_owner
    out = {
        "id": run.id,
        "chain_id": run.chain_id,
        "chain_name": chain_name,
        "status": run.status,
        "content": run.content,
        "error": run.error,
        "summary": run.summary,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "read_at": run.read_at.isoformat() if run.read_at else None,
    }
    if not viewer_only:
        out["usage"] = run.usage
        out["approval_id"] = run.approval_id
        out["audit_trail"] = run.audit_trail
    if run.status == "awaiting_approval" and not viewer_only:
        approval = (
            await db.execute(
                select(ChainApprovalRequest).where(ChainApprovalRequest.id == run.approval_id)
            )
        ).scalar_one_or_none()
        if approval and approval.state_snapshot:
            main_edges = approval.state_snapshot.get("main_edges", [])
            approval_node_id = approval.approval_node_id
            main_nodes = approval.state_snapshot.get("main_nodes", {})
            next_stages = []
            for e in main_edges:
                if e.get("source") != approval_node_id:
                    continue
                tgt = e.get("target")
                if tgt in main_nodes:
                    tn = main_nodes[tgt]
                    if tn.get("type") == "slug":
                        label = f"Slug: {tn.get('slug', tgt)}"
                    else:
                        label = tn.get("agent_id") and f"Agent #{tn['agent_id']}" or tgt
                    next_stages.append({"node_id": tgt, "label": label})
            out["next_stages"] = next_stages
    return out


@router.patch("/runs/{run_id}/read")
async def mark_chain_run_read(
    run_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a run as read (clears from unread notification count). Allowed if user can view run."""
    from datetime import datetime, timezone
    result = await db.execute(
        select(ChainRun, AgentChain.workspace_id).where(ChainRun.id == run_id).join(
            AgentChain, ChainRun.chain_id == AgentChain.id
        )
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(404, "Run not found")
    run, chain_workspace_id = row[0], row[1]
    is_owner = run.user_id == user.id
    member = await get_workspace_member(db, chain_workspace_id, user.id) if chain_workspace_id else None
    if not is_owner and not (member and (can_view_runs(member.role) or can_view_outputs_only(member.role))):
        raise HTTPException(404, "Run not found")
    run.read_at = datetime.now(timezone.utc)
    await db.commit()
    return {"run_id": run_id, "read_at": run.read_at.isoformat()}


@router.post("/runs/{run_id}/share")
async def create_run_share_link(
    run_id: int,
    payload: RunShareCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a share link for run output (private tokenized URL, optional expiry). User must be able to view run."""
    result = await db.execute(
        select(ChainRun, AgentChain.workspace_id).where(ChainRun.id == run_id).join(
            AgentChain, ChainRun.chain_id == AgentChain.id
        )
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(404, "Run not found")
    run, chain_workspace_id = row[0], row[1]
    is_owner = run.user_id == user.id
    member = await get_workspace_member(db, chain_workspace_id, user.id) if chain_workspace_id else None
    if not is_owner and not (member and (can_view_runs(member.role) or can_view_outputs_only(member.role))):
        raise HTTPException(404, "Run not found")
    expires_at = None
    if payload.expires_in_seconds is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=payload.expires_in_seconds)
    token = secrets.token_urlsafe(32)
    link = RunShareLink(run_id=run_id, token=token, expires_at=expires_at)
    db.add(link)
    await db.commit()
    return {
        "token": token,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "url": f"/share/run/{token}",
    }


@router.get("/runs/{job_id}")
async def get_chain_run_status(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Poll chain run status and result. Persists result to chain_runs when task finishes."""
    from app.worker.celery_app import celery_app
    from datetime import datetime

    stored = CHAIN_JOB_STORE.get(job_id)
    if isinstance(stored, tuple):
        task_id, _user_id, run_id = stored[0], stored[1], stored[2] if len(stored) > 2 else None
    else:
        task_id, run_id = stored, None
    if not task_id:
        raise HTTPException(404, "Job not found")
    result = AsyncResult(task_id, app=celery_app)
    if result.state == "PENDING":
        return {"job_id": job_id, "status": "pending", "run_id": run_id}
    if result.state == "SUCCESS":
        data = result.result or {}
        if data.get("status") == "awaiting_approval":
            approval_id = data.get("approval_id")
            summary = data.get("summary", "")
            next_stages = data.get("next_stages", [])
            if run_id:
                run_row = (await db.execute(select(ChainRun).where(ChainRun.id == run_id))).scalar_one_or_none()
                if run_row and run_row.user_id == user.id:
                    run_row.status = "awaiting_approval"
                    run_row.approval_id = approval_id
                    run_row.summary = summary
                    await db.commit()
            return {
                "job_id": job_id,
                "run_id": run_id,
                "status": "awaiting_approval",
                "approval_id": approval_id,
                "summary": summary,
                "next_stages": next_stages,
                "usage": data.get("usage"),
            }
        content = data.get("content")
        if content and any(
            x in (content or "")
            for x in ("Docker error", "Sandbox image", "Execution error", "No response file", "Error:")
        ):
            content = _sanitize_error(content) if content else content
        if run_id:
            run_row = (await db.execute(select(ChainRun).where(ChainRun.id == run_id))).scalar_one_or_none()
            if run_row and run_row.user_id == user.id:
                run_row.status = "completed"
                run_row.content = content
                run_row.usage = data.get("usage")
                await db.commit()
        return {"job_id": job_id, "run_id": run_id, "status": "completed", "content": content, "usage": data.get("usage")}
    if result.state == "FAILURE":
        err_msg = _sanitize_error(str(result.result))
        if run_id:
            run_row = (await db.execute(select(ChainRun).where(ChainRun.id == run_id))).scalar_one_or_none()
            if run_row and run_row.user_id == user.id:
                run_row.status = "error"
                run_row.error = err_msg
                await db.commit()
        return {"job_id": job_id, "run_id": run_id, "status": "error", "error": err_msg}
    return {"job_id": job_id, "run_id": run_id, "status": result.state.lower()}


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
    is_workspace_member_can_view = False
    if not is_public and not is_owner_or_staff and user and chain.workspace_id is not None:
        member = await get_workspace_member(db, chain.workspace_id, user.id)
        if member and can_view_runs(member.role):
            is_workspace_member_can_view = True
    if not is_public and not is_owner_or_staff and not is_workspace_member_can_view:
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


def _can_edit_chain(chain: AgentChain, user: User, member: WorkspaceMember | None) -> bool:
    if chain.expert_id == user.id or user.role.value == "admin":
        return True
    if chain.workspace_id is not None and member and can_edit_teams(member.role):
        return True
    return False


@router.put("/{chain_id}", response_model=ChainResponse)
async def update_chain(
    chain_id: int,
    payload: ChainUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update authored chain draft/rejected chain (owner or workspace member with edit)."""
    if user.role.value not in ("expert", "admin"):
        raise HTTPException(403, "Expert or admin access required")
    result = await db.execute(select(AgentChain).where(AgentChain.id == chain_id))
    chain = result.scalar_one_or_none()
    if not chain:
        raise HTTPException(404, "Chain not found")
    member = await get_workspace_member(db, chain.workspace_id, user.id) if chain.workspace_id else None
    if not _can_edit_chain(chain, user, member):
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
    if payload.slug is not None:
        chain.slug = payload.slug or None

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
    result = await db.execute(select(AgentChain).where(AgentChain.id == chain_id))
    chain = result.scalar_one_or_none()
    if not chain:
        raise HTTPException(404, "Chain not found")
    member = await get_workspace_member(db, chain.workspace_id, user.id) if chain.workspace_id else None
    if not _can_edit_chain(chain, user, member):
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
    result = await db.execute(select(AgentChain).where(AgentChain.id == chain_id))
    chain = result.scalar_one_or_none()
    if not chain:
        raise HTTPException(404, "Chain not found")
    member = await get_workspace_member(db, chain.workspace_id, user.id) if chain.workspace_id else None
    if not _can_edit_chain(chain, user, member):
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
    if payload.personality_id and chain.workspace_id:
        from app.models.workspace_personality import WorkspacePersonality
        pers_result = await db.execute(
            select(WorkspacePersonality).where(
                WorkspacePersonality.id == payload.personality_id,
                WorkspacePersonality.workspace_id == chain.workspace_id,
            )
        )
        pers = pers_result.scalar_one_or_none()
        if pers and (pers.content or "").strip():
            personality_text = pers.content.strip()
    if not personality_text:
        profile_result = await db.execute(
            select(UserPersonalityProfile).where(UserPersonalityProfile.user_id == user.id)
        )
        profile = profile_result.scalar_one_or_none()
        if profile and (profile.profile_text or "").strip():
            personality_text = profile.profile_text.strip()

    github_token = None
    gh_result = await db.execute(
        select(UserGitHubToken).where(UserGitHubToken.user_id == user.id)
    )
    gh_row = gh_result.scalar_one_or_none()
    if gh_row:
        github_token = decrypt_api_key(gh_row.encrypted_token)
    defn = chain.definition or {}
    agent_ids = {n.get("agent_id") for n in defn.get("nodes", []) if n.get("agent_id") is not None}
    if agent_ids and not github_token:
        agents_result = await db.execute(select(Agent).where(Agent.id.in_(agent_ids)))
        agents_list = agents_result.scalars().all()
        if any(manifest_has_github_module(a.manifest or {}) for a in agents_list):
            raise HTTPException(
                400,
                "This chain uses GitHub. Add a GitHub token in settings (e.g. Users / GitHub token) first.",
            )

    from app.worker.tasks import run_chain_task, run_commit_analysis_loop_task, _extract_loop_config

    run = ChainRun(
        user_id=user.id,
        chain_id=chain_id,
        status="queued",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    input_run_refs_valid = None
    if payload.input_run_refs:
        refs_valid = []
        for ref in payload.input_run_refs:
            if ref.source == "chain":
                cr = (await db.execute(select(ChainRun, AgentChain.workspace_id).where(
                    ChainRun.id == ref.run_id
                ).join(AgentChain, ChainRun.chain_id == AgentChain.id))).one_or_none()
                if not cr:
                    raise HTTPException(400, f"Chain run {ref.run_id} not found")
                run_row, ws_id = cr[0], cr[1]
                is_owner = run_row.user_id == user.id
                member = await get_workspace_member(db, ws_id, user.id) if ws_id else None
                can_view = is_owner or (member and (can_view_runs(member.role) or can_view_outputs_only(member.role)))
                if not can_view:
                    raise HTTPException(403, f"Cannot use chain run {ref.run_id}")
                refs_valid.append({"source": "chain", "run_id": ref.run_id})
            elif ref.source == "agent":
                ar = (await db.execute(select(AgentRun).where(AgentRun.id == ref.run_id))).scalar_one_or_none()
                if not ar:
                    raise HTTPException(400, f"Agent run {ref.run_id} not found")
                if ar.user_id != user.id:
                    raise HTTPException(403, f"Cannot use agent run {ref.run_id}")
                refs_valid.append({"source": "agent", "run_id": ref.run_id})
            else:
                raise HTTPException(400, f"Invalid run source: {ref.source}")
        input_run_refs_valid = refs_valid

    job_id = str(uuid4())
    loop_config = _extract_loop_config(defn)
    use_loop_task = loop_config is not None and payload.run_type != "setup"
    if use_loop_task:
        task = run_commit_analysis_loop_task.delay(
            chain_id=chain_id,
            user_input=payload.user_input,
            model=payload.model,
            api_key=api_key,
            buyer_id=user.id if not payload.use_byok else None,
            run_owner_id=user.id,
            github_token=github_token,
            run_id=run.id,
            personality_text=personality_text,
        )
    else:
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
            run_id=run.id,
            input_run_refs=input_run_refs_valid,
        )
    run.job_id = job_id
    await db.commit()
    CHAIN_JOB_STORE[job_id] = (task.id, user.id, run.id)
    return {"job_id": job_id, "run_id": run.id, "status": "queued"}


@router.post("/approvals/{approval_id}/approve")
async def approve_chain_run(
    approval_id: int,
    payload: ChainApprovalApproveRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve or reject an approval request. On approve, enqueues resume task and returns new job_id for polling."""
    approval = (
        await db.execute(
            select(ChainApprovalRequest).where(ChainApprovalRequest.id == approval_id)
        )
    ).scalar_one_or_none()
    if not approval:
        raise HTTPException(404, "Approval not found")
    if approval.user_id != user.id:
        raise HTTPException(403, "Only the run owner can approve or reject")
    if approval.status != "pending":
        raise HTTPException(400, "Approval already decided")
    if not payload.approved:
        approval.status = "rejected"
        await db.commit()
        return {"approved": False, "status": "rejected"}

    api_key = None
    profile_result = await db.execute(
        select(UserPersonalityProfile).where(UserPersonalityProfile.user_id == user.id)
    )
    profile = profile_result.scalar_one_or_none()
    personality_text = (profile.profile_text or "").strip() if profile else ""
    gh_result = await db.execute(
        select(UserGitHubToken).where(UserGitHubToken.user_id == user.id)
    )
    gh_row = gh_result.scalar_one_or_none()
    github_token = decrypt_api_key(gh_row.encrypted_token) if gh_row else None
    key_result = await db.execute(
        select(UserLLMKey).where(UserLLMKey.user_id == user.id, UserLLMKey.provider == "openai")
    )
    key_row = key_result.scalar_one_or_none()
    if key_row:
        api_key = decrypt_api_key(key_row.encrypted_key)

    from app.worker.tasks import resume_chain_task
    job_id = str(uuid4())
    run_row = (
        await db.execute(select(ChainRun).where(ChainRun.approval_id == approval_id))
    ).scalar_one_or_none()
    run_row_id = run_row.id if run_row else None
    task = resume_chain_task.delay(
        approval_id=approval_id,
        user_input="",
        model="openai/gpt-5.2",
        api_key=api_key,
        buyer_id=user.id,
        personality_text=personality_text or None,
        github_token=github_token,
        next_stage_node_id=payload.next_stage_node_id,
        run_id=run_row_id,
    )
    if run_row:
        run_row.job_id = job_id
        run_row.status = "resuming"
        await db.commit()
        run_id = run_row.id
    else:
        run_id = None
    CHAIN_JOB_STORE[job_id] = (task.id, user.id, run_id)
    return {"approved": True, "job_id": job_id, "run_id": run_id, "status": "resuming"}
