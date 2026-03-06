"""Workspace, members, and secrets endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_workspace_member, require_workspace_role
from app.db.session import get_db
from app.core.key_encryption import encrypt_api_key
from app.core.workspace_permissions import can_manage_secrets
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.models.workspace_secret import WorkspaceSecret
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceUpdate,
    WorkspaceResponse,
    WorkspaceListResponse,
    MemberResponse,
    MemberInvite,
    MemberUpdateRole,
    SecretCreate,
    SecretListItem,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

ALLOWED_INVITE_ROLES = ("admin", "member", "viewer")


@router.get("/", response_model=list[WorkspaceListResponse])
async def list_workspaces(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List workspaces where current user is a member (with role)."""
    result = await db.execute(
        select(Workspace, WorkspaceMember.role)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user.id)
        .order_by(Workspace.name)
    )
    rows = result.all()
    return [
        WorkspaceListResponse(
            id=w.id,
            name=w.name,
            slug=w.slug,
            role=role,
            created_at=w.created_at,
        )
        for w, role in rows
    ]


@router.post("/", response_model=WorkspaceResponse)
async def create_workspace(
    body: WorkspaceCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create workspace and add current user as Owner."""
    workspace = Workspace(name=body.name, slug=body.slug)
    db.add(workspace)
    await db.flush()
    member = WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
    db.add(member)
    await db.commit()
    await db.refresh(workspace)
    return workspace


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get workspace by id (members only)."""
    await require_workspace_role(db, workspace_id, user, ["owner", "admin", "member", "viewer"])
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    return workspace


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: int,
    body: WorkspaceUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update workspace name/slug (Owner/Admin)."""
    await require_workspace_role(db, workspace_id, user, ["owner", "admin"])
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    if body.name is not None:
        workspace.name = body.name
    if body.slug is not None:
        workspace.slug = body.slug
    await db.commit()
    await db.refresh(workspace)
    return workspace


# ---- Members ----

@router.get("/{workspace_id}/members", response_model=list[MemberResponse])
async def list_members(
    workspace_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List workspace members (any member can list)."""
    await require_workspace_role(db, workspace_id, user, ["owner", "admin", "member", "viewer"])
    result = await db.execute(
        select(WorkspaceMember, User.email)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.created_at)
    )
    rows = result.all()
    return [
        MemberResponse(
            user_id=wm.user_id,
            email=email,
            role=wm.role,
            created_at=wm.created_at,
        )
        for wm, email in rows
    ]


@router.post("/{workspace_id}/members", response_model=MemberResponse)
async def add_member(
    workspace_id: int,
    body: MemberInvite,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Invite user by email (Owner/Admin). Creates or updates membership."""
    await require_workspace_role(db, workspace_id, user, ["owner", "admin"])
    if body.role not in ALLOWED_INVITE_ROLES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid role")
    result = await db.execute(select(User).where(User.email == body.email.lower()))
    invited_user = result.scalar_one_or_none()
    if not invited_user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    existing = await get_workspace_member(db, workspace_id, invited_user.id)
    if existing:
        existing.role = body.role
        await db.commit()
        await db.refresh(existing)
        result = await db.execute(select(User).where(User.id == invited_user.id))
        u = result.scalar_one()
        return MemberResponse(
            user_id=existing.user_id,
            email=u.email,
            role=existing.role,
            created_at=existing.created_at,
        )
    member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=invited_user.id,
        role=body.role,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return MemberResponse(
        user_id=member.user_id,
        email=body.email,
        role=member.role,
        created_at=member.created_at,
    )


@router.patch("/{workspace_id}/members/{member_user_id}", response_model=MemberResponse)
async def update_member_role(
    workspace_id: int,
    member_user_id: int,
    body: MemberUpdateRole,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change member role (Owner/Admin). Cannot change own role if only owner."""
    await require_workspace_role(db, workspace_id, user, ["owner", "admin"])
    if body.role not in ALLOWED_INVITE_ROLES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid role")
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == member_user_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    if member.role == "owner" and member_user_id == user.id:
        owners = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.role == "owner",
            )
        )
        if len(owners.scalars().all()) <= 1:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Cannot change role of the only owner",
            )
    member.role = body.role
    await db.commit()
    await db.refresh(member)
    result = await db.execute(select(User).where(User.id == member_user_id))
    u = result.scalar_one()
    return MemberResponse(
        user_id=member.user_id,
        email=u.email,
        role=member.role,
        created_at=member.created_at,
    )


@router.delete("/{workspace_id}/members/{member_user_id}")
async def remove_member(
    workspace_id: int,
    member_user_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove member (Owner/Admin). Cannot remove last owner."""
    await require_workspace_role(db, workspace_id, user, ["owner", "admin"])
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == member_user_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    if member.role == "owner":
        owners = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.role == "owner",
            )
        )
        if len(owners.scalars().all()) <= 1:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Cannot remove the only owner",
            )
    await db.delete(member)
    await db.commit()
    return {"ok": True}


# ---- Secrets ----

@router.get("/{workspace_id}/secrets", response_model=list[SecretListItem])
async def list_secrets(
    workspace_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List secret key names (and optional chain_id). Owner/Admin only."""
    member = await require_workspace_role(db, workspace_id, user, ["owner", "admin"])
    if not can_manage_secrets(member.role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot manage secrets")
    result = await db.execute(
        select(WorkspaceSecret)
        .where(WorkspaceSecret.workspace_id == workspace_id)
        .order_by(WorkspaceSecret.key_name, WorkspaceSecret.chain_id)
    )
    secrets = result.scalars().all()
    return [
        SecretListItem(
            key_name=s.key_name,
            chain_id=s.chain_id,
            created_at=s.created_at,
        )
        for s in secrets
    ]


@router.post("/{workspace_id}/secrets")
async def create_or_update_secret(
    workspace_id: int,
    body: SecretCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set workspace secret (key_name, value, optional chain_id). Owner/Admin only."""
    member = await require_workspace_role(db, workspace_id, user, ["owner", "admin"])
    if not can_manage_secrets(member.role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot manage secrets")
    q = select(WorkspaceSecret).where(
        WorkspaceSecret.workspace_id == workspace_id,
        WorkspaceSecret.key_name == body.key_name,
    )
    if body.chain_id is not None:
        q = q.where(WorkspaceSecret.chain_id == body.chain_id)
    else:
        q = q.where(WorkspaceSecret.chain_id.is_(None))
    result = await db.execute(q)
    existing = result.scalar_one_or_none()
    encrypted = encrypt_api_key(body.value)
    if existing:
        existing.encrypted_value = encrypted
        await db.commit()
        return {"key_name": body.key_name, "chain_id": body.chain_id, "updated": True}
    secret = WorkspaceSecret(
        workspace_id=workspace_id,
        chain_id=body.chain_id,
        key_name=body.key_name,
        encrypted_value=encrypted,
    )
    db.add(secret)
    await db.commit()
    return {"key_name": body.key_name, "chain_id": body.chain_id, "created": True}


@router.delete("/{workspace_id}/secrets/{key_name}")
async def delete_secret(
    workspace_id: int,
    key_name: str,
    chain_id: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete secret by key_name and optional chain_id. Owner/Admin only."""
    member = await require_workspace_role(db, workspace_id, user, ["owner", "admin"])
    if not can_manage_secrets(member.role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot manage secrets")
    q = select(WorkspaceSecret).where(
        WorkspaceSecret.workspace_id == workspace_id,
        WorkspaceSecret.key_name == key_name,
    )
    if chain_id is not None:
        q = q.where(WorkspaceSecret.chain_id == chain_id)
    else:
        q = q.where(WorkspaceSecret.chain_id.is_(None))
    result = await db.execute(q)
    secret = result.scalar_one_or_none()
    if not secret:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Secret not found")
    await db.delete(secret)
    await db.commit()
    return {"ok": True}
