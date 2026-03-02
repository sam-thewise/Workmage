"""User profile and integration settings (e.g. GitHub token for MCP)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.key_encryption import encrypt_api_key
from app.db.session import get_db
from app.models.user import User
from app.models.user_github_token import UserGitHubToken

router = APIRouter(prefix="/users", tags=["users"])


def _is_github_token_format(token: str) -> bool:
    """Accept ghp_, github_pat_, or other common GitHub token prefixes."""
    if not token or len(token) < 20:
        return False
    return (
        token.startswith("ghp_")
        or token.startswith("github_pat_")
        or token.startswith("gho_")
    )


class GitHubTokenRequest(BaseModel):
    token: str


@router.post("/me/github-token")
async def save_github_token(
    payload: GitHubTokenRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save user's GitHub token (encrypted at rest). Required for agents that use GitHub MCP tools."""
    if not _is_github_token_format(payload.token):
        raise HTTPException(
            400,
            "Invalid GitHub token. Use a personal access token (ghp_...) or fine-grained token (github_pat_...).",
        )
    encrypted = encrypt_api_key(payload.token)
    result = await db.execute(
        select(UserGitHubToken).where(UserGitHubToken.user_id == user.id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.encrypted_token = encrypted
    else:
        db.add(UserGitHubToken(user_id=user.id, encrypted_token=encrypted))
    await db.commit()
    return {"status": "saved"}


@router.delete("/me/github-token")
async def delete_github_token(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove user's stored GitHub token."""
    result = await db.execute(
        select(UserGitHubToken).where(UserGitHubToken.user_id == user.id)
    )
    row = result.scalar_one_or_none()
    if row:
        await db.delete(row)
        await db.commit()
    return {"status": "deleted"}
