"""API dependencies."""
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.security import verify_password
from app.core.workspace_permissions import (
    can_manage_secrets,
    can_manage_billing_members_teams,
    can_edit_teams,
    can_run_teams,
    can_view_runs,
    can_view_outputs_only,
)
from app.db.session import get_db
from app.models.user import User
from app.models.workspace_member import WorkspaceMember

security = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> User | None:
    """Get current user if token provided, else None."""
    if not credentials:
        return None
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        user_id: str | None = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        return None

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    return user


async def get_current_user(
    user: Annotated[User | None, Depends(get_current_user_optional)],
) -> User:
    """Get current user, raise 401 if not authenticated."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


async def get_current_active_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get current active user."""
    return user


async def get_admin_or_moderator(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get current user, require admin or moderator role."""
    if user.role.value not in ("admin", "moderator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or moderator access required",
        )
    return user


async def get_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get current user, require admin role."""
    if user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


async def get_workspace_member(
    db: AsyncSession,
    workspace_id: int,
    user_id: int,
) -> WorkspaceMember | None:
    """Return workspace membership for user if any."""
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def require_workspace_role(
    db: AsyncSession,
    workspace_id: int,
    user: User,
    allowed_roles: list[str],
) -> WorkspaceMember:
    """Require user to be a member of the workspace with one of the allowed roles. Raises 403 otherwise."""
    member = await get_workspace_member(db, workspace_id, user.id)
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this workspace",
        )
    if member.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role in this workspace",
        )
    return member
