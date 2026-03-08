"""Wizard endpoints: use cases for config-driven setup wizard."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_admin_or_moderator
from app.db.session import get_db
from app.models.chain import AgentChain
from app.models.chain_run import ChainRun
from app.models.agent_run import AgentRun
from app.models.wizard_use_case import WizardUseCase

router = APIRouter(prefix="/wizard", tags=["wizard"])


class ParamDef(BaseModel):
    slug: str
    label: str
    type: str = "text"
    required: bool = False
    placeholder: str | None = None
    validation: str | None = None
    options: list[str] | None = None
    default: str | None = None


class WizardUseCaseResponse(BaseModel):
    id: int
    slug: str
    label: str
    description: str | None
    chain_slug: str
    chain_id: int | None
    params: list[dict]
    inject_as: str
    required_config: list[str]
    sort_order: int


class WizardUseCaseCreate(BaseModel):
    slug: str = Field(..., min_length=1, max_length=120)
    label: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    chain_slug: str = Field(..., min_length=1, max_length=120)
    params: list[dict] = Field(default_factory=list)
    inject_as: str = Field(default="slugs", pattern="^(slugs|user_input|run_history)$")
    required_config: list[str] = Field(default_factory=list)
    sort_order: int = 0


class WizardUseCaseUpdate(BaseModel):
    label: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    chain_slug: str | None = Field(None, min_length=1, max_length=120)
    params: list[dict] | None = None
    inject_as: str | None = Field(None, pattern="^(slugs|user_input|run_history)$")
    required_config: list[str] | None = None
    sort_order: int | None = None


def _slug_valid(slug: str) -> bool:
    if not slug or len(slug) > 120:
        return False
    return slug.replace("_", "").replace("-", "").isalnum()


KNOWN_CONFIG_KEYS = frozenset({"github_token"})
CONFIG_LABELS = {"github_token": "GitHub token", "llm_key": "LLM API key"}


async def _check_config_status(db: AsyncSession, user_id: int, keys: list[str]) -> dict[str, bool]:
    """Check which config keys the user has. Returns {key: has_config} for known keys."""
    out: dict[str, bool] = {}
    for k in keys:
        if k not in KNOWN_CONFIG_KEYS:
            out[k] = False
            continue
        if k == "github_token":
            from sqlalchemy import select
            from app.models.user_github_token import UserGitHubToken
            r = await db.execute(select(UserGitHubToken).where(UserGitHubToken.user_id == user_id))
            out[k] = r.scalar_one_or_none() is not None
        else:
            out[k] = False
    return out


@router.get("/config-status")
async def get_config_status(
    keys: str = "github_token",
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check whether the current user has the requested config (e.g. github_token). keys=github_token or comma-separated."""
    key_list = [k.strip() for k in keys.split(",") if k.strip()]
    status = await _check_config_status(db, user.id, key_list)
    return status


@router.get("/status")
async def get_wizard_status(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return runs_count for the current user. Used for first-login redirect (runs_count === 0 -> show wizard)."""
    chain_count = await db.execute(
        select(func.count(ChainRun.id)).where(ChainRun.user_id == user.id)
    )
    agent_count = await db.execute(
        select(func.count(AgentRun.id)).where(AgentRun.user_id == user.id)
    )
    total = (chain_count.scalar() or 0) + (agent_count.scalar() or 0)
    return {"runs_count": total}


async def _resolve_chain_id(db: AsyncSession, chain_slug: str) -> int | None:
    """Resolve chain_slug to chain_id. Returns None if not found."""
    result = await db.execute(
        select(AgentChain.id).where(AgentChain.slug == chain_slug)
    )
    row = result.first()
    return row[0] if row else None


@router.get("/use-cases", response_model=list[WizardUseCaseResponse])
async def list_use_cases(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List wizard use cases for the setup wizard. Resolves chain_slug to chain_id."""
    result = await db.execute(
        select(WizardUseCase)
        .order_by(WizardUseCase.sort_order.asc(), WizardUseCase.id.asc())
    )
    use_cases = result.scalars().all()
    out = []
    for uc in use_cases:
        chain_id = await _resolve_chain_id(db, uc.chain_slug)
        out.append(
            WizardUseCaseResponse(
                id=uc.id,
                slug=uc.slug,
                label=uc.label,
                description=uc.description,
                chain_slug=uc.chain_slug,
                chain_id=chain_id,
                params=uc.params or [],
                inject_as=uc.inject_as,
                required_config=uc.required_config or [],
                sort_order=uc.sort_order,
            )
        )
    return out


# --- Admin CRUD ---


@router.get("/admin/use-cases", response_model=list[dict])
async def admin_list_use_cases(
    user=Depends(get_admin_or_moderator),
    db: AsyncSession = Depends(get_db),
):
    """Admin: list all wizard use cases."""
    result = await db.execute(
        select(WizardUseCase)
        .order_by(WizardUseCase.sort_order.asc(), WizardUseCase.id.asc())
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "slug": r.slug,
            "label": r.label,
            "description": r.description,
            "chain_slug": r.chain_slug,
            "params": r.params or [],
            "inject_as": r.inject_as,
            "required_config": getattr(r, "required_config", None) or [],
            "sort_order": r.sort_order,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]


@router.post("/admin/use-cases", response_model=dict)
async def admin_create_use_case(
    payload: WizardUseCaseCreate,
    user=Depends(get_admin_or_moderator),
    db: AsyncSession = Depends(get_db),
):
    """Admin: create a wizard use case."""
    if not _slug_valid(payload.slug):
        raise HTTPException(400, "Invalid slug: alphanumeric, hyphens, underscores only")
    existing = await db.execute(
        select(WizardUseCase).where(WizardUseCase.slug == payload.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, f"Use case slug already exists: {payload.slug}")
    uc = WizardUseCase(
        slug=payload.slug,
        label=payload.label,
        description=payload.description,
        chain_slug=payload.chain_slug,
        params=payload.params,
        inject_as=payload.inject_as,
        required_config=payload.required_config or [],
        sort_order=payload.sort_order,
    )
    db.add(uc)
    await db.commit()
    await db.refresh(uc)
    return {
        "id": uc.id,
        "slug": uc.slug,
        "label": uc.label,
        "description": uc.description,
        "chain_slug": uc.chain_slug,
        "params": uc.params or [],
        "inject_as": uc.inject_as,
        "required_config": getattr(uc, "required_config", None) or [],
        "sort_order": uc.sort_order,
        "created_at": uc.created_at.isoformat() if uc.created_at else None,
        "updated_at": uc.updated_at.isoformat() if uc.updated_at else None,
    }


@router.get("/admin/use-cases/{use_case_id}", response_model=dict)
async def admin_get_use_case(
    use_case_id: int,
    user=Depends(get_admin_or_moderator),
    db: AsyncSession = Depends(get_db),
):
    """Admin: get one wizard use case."""
    result = await db.execute(
        select(WizardUseCase).where(WizardUseCase.id == use_case_id)
    )
    uc = result.scalar_one_or_none()
    if not uc:
        raise HTTPException(404, "Use case not found")
    return {
        "id": uc.id,
        "slug": uc.slug,
        "label": uc.label,
        "description": uc.description,
        "chain_slug": uc.chain_slug,
        "params": uc.params or [],
        "inject_as": uc.inject_as,
        "required_config": getattr(uc, "required_config", None) or [],
        "sort_order": uc.sort_order,
        "created_at": uc.created_at.isoformat() if uc.created_at else None,
        "updated_at": uc.updated_at.isoformat() if uc.updated_at else None,
    }


@router.put("/admin/use-cases/{use_case_id}", response_model=dict)
async def admin_update_use_case(
    use_case_id: int,
    payload: WizardUseCaseUpdate,
    user=Depends(get_admin_or_moderator),
    db: AsyncSession = Depends(get_db),
):
    """Admin: update a wizard use case."""
    result = await db.execute(
        select(WizardUseCase).where(WizardUseCase.id == use_case_id)
    )
    uc = result.scalar_one_or_none()
    if not uc:
        raise HTTPException(404, "Use case not found")
    if payload.label is not None:
        uc.label = payload.label
    if payload.description is not None:
        uc.description = payload.description
    if payload.chain_slug is not None:
        uc.chain_slug = payload.chain_slug
    if payload.params is not None:
        uc.params = payload.params
    if payload.inject_as is not None:
        uc.inject_as = payload.inject_as
    if payload.required_config is not None:
        uc.required_config = payload.required_config
    if payload.sort_order is not None:
        uc.sort_order = payload.sort_order
    await db.commit()
    await db.refresh(uc)
    return {
        "id": uc.id,
        "slug": uc.slug,
        "label": uc.label,
        "description": uc.description,
        "chain_slug": uc.chain_slug,
        "params": uc.params or [],
        "inject_as": uc.inject_as,
        "required_config": getattr(uc, "required_config", None) or [],
        "sort_order": uc.sort_order,
        "created_at": uc.created_at.isoformat() if uc.created_at else None,
        "updated_at": uc.updated_at.isoformat() if uc.updated_at else None,
    }


@router.delete("/admin/use-cases/{use_case_id}", status_code=204)
async def admin_delete_use_case(
    use_case_id: int,
    user=Depends(get_admin_or_moderator),
    db: AsyncSession = Depends(get_db),
):
    """Admin: delete a wizard use case."""
    result = await db.execute(
        select(WizardUseCase).where(WizardUseCase.id == use_case_id)
    )
    uc = result.scalar_one_or_none()
    if not uc:
        raise HTTPException(404, "Use case not found")
    await db.delete(uc)
    await db.commit()
    return None
