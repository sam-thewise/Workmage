"""Personality profile API: get/update profile, analyze tweets to produce profile."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_workspace_role
from app.core.config import settings
from app.core.key_encryption import decrypt_api_key
from app.db.session import get_db
from app.core.workspace_permissions import can_edit_teams
from app.models.user import User
from app.models.user_llm_key import UserLLMKey
from app.models.user_personality import UserPersonalityProfile
from app.models.workspace_personality import WorkspacePersonality
from app.services.personality_service import analyze_tweets_to_profile

router = APIRouter(prefix="/personality", tags=["personality"])


class PersonalityResponse(BaseModel):
    profile_text: str
    source_sample: str | None
    updated_at: str | None


class PersonalityUpdate(BaseModel):
    profile_text: str = Field(..., min_length=1)


class PersonalityAnalyzeRequest(BaseModel):
    tweet_text: str | None = Field(None, description="Raw tweet/post text to analyze")
    twstalker_url: str | None = Field(None, max_length=512, description="twstalker.com profile URL to scrape then analyze")
    save: bool = Field(False, description="If true, save the analyzed profile after returning it")
    model: str = Field("openai/gpt-5-mini", description="Model for analysis")
    workspace_id: int | None = Field(None, description="If set with personality_name, save to workspace personality")
    chain_id: int | None = Field(None, description="Optional chain (team) scope for workspace personality")
    personality_name: str | None = Field(None, description="Name for workspace personality (requires workspace_id)")


def _profile_to_response(p: UserPersonalityProfile | None) -> PersonalityResponse | None:
    if not p:
        return None
    return PersonalityResponse(
        profile_text=p.profile_text or "",
        source_sample=p.source_sample,
        updated_at=p.updated_at.isoformat() if p.updated_at else None,
    )


@router.get("", response_model=PersonalityResponse | None)
async def get_my_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's personality profile (voice/beliefs for content)."""
    result = await db.execute(
        select(UserPersonalityProfile).where(UserPersonalityProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    return _profile_to_response(profile)


@router.put("", response_model=PersonalityResponse)
async def update_my_profile(
    payload: PersonalityUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update personality profile (editable after import/analyze)."""
    result = await db.execute(
        select(UserPersonalityProfile).where(UserPersonalityProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    if profile:
        profile.profile_text = payload.profile_text
    else:
        profile = UserPersonalityProfile(user_id=user.id, profile_text=payload.profile_text)
        db.add(profile)
    await db.commit()
    await db.refresh(profile)
    out = _profile_to_response(profile)
    assert out is not None
    return out


@router.post("/analyze", response_model=PersonalityResponse)
async def analyze_tweets(
    payload: PersonalityAnalyzeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Analyze tweet text (or scrape twstalker URL) to produce a personality profile. Optionally save."""
    tweet_text = (payload.tweet_text or "").strip()
    if payload.twstalker_url:
        from app.api.v1.endpoints.mcp import _scrape_as_markdown
        try:
            scraped = _scrape_as_markdown(payload.twstalker_url.strip(), max_length=50000)
            tweet_text = (tweet_text + "\n\n" + scraped).strip() if tweet_text else scraped
        except Exception as e:
            raise HTTPException(400, f"Could not fetch URL: {e}")
    if not tweet_text:
        raise HTTPException(400, "Provide either tweet_text or twstalker_url")

    api_key = None
    provider = payload.model.split("/")[0] if "/" in payload.model else "openai"
    if provider in ("openai", "anthropic"):
        key_result = await db.execute(
            select(UserLLMKey).where(
                UserLLMKey.user_id == user.id,
                UserLLMKey.provider == provider,
            )
        )
        row = key_result.scalar_one_or_none()
        if row:
            api_key = decrypt_api_key(row.encrypted_key)
        if not api_key and provider == "openai":
            api_key = getattr(settings, "OPENAI_API_KEY", "") or None
        if not api_key and provider == "anthropic":
            api_key = getattr(settings, "ANTHROPIC_API_KEY", "") or None

    profile_text = analyze_tweets_to_profile(tweet_text, model=payload.model, api_key=api_key)
    if not profile_text:
        raise HTTPException(502, "Analysis produced no output")

    # Save to workspace personality if workspace_id + personality_name provided
    if payload.workspace_id is not None and payload.personality_name:
        member = await require_workspace_role(
            db, payload.workspace_id, user, ["owner", "admin", "member"]
        )
        if not can_edit_teams(member.role):
            raise HTTPException(403, "Cannot create workspace personalities")
        q = select(WorkspacePersonality).where(
            WorkspacePersonality.workspace_id == payload.workspace_id,
            WorkspacePersonality.name == payload.personality_name.strip(),
        )
        if payload.chain_id is not None:
            q = q.where(WorkspacePersonality.chain_id == payload.chain_id)
        else:
            q = q.where(WorkspacePersonality.chain_id.is_(None))
        result = await db.execute(q)
        existing_row = result.scalar_one_or_none()
        if existing_row:
            existing_row.content = profile_text
            existing_row.source = "analyze"
            await db.commit()
            await db.refresh(existing_row)
        else:
            wp = WorkspacePersonality(
                workspace_id=payload.workspace_id,
                chain_id=payload.chain_id,
                name=payload.personality_name.strip(),
                content=profile_text,
                source="analyze",
            )
            db.add(wp)
            await db.commit()
            await db.refresh(wp)

    if payload.save:
        result = await db.execute(
            select(UserPersonalityProfile).where(UserPersonalityProfile.user_id == user.id)
        )
        profile = result.scalar_one_or_none()
        if profile:
            profile.profile_text = profile_text
            profile.source_sample = tweet_text[:20000] if len(tweet_text) > 20000 else tweet_text
        else:
            profile = UserPersonalityProfile(
                user_id=user.id,
                profile_text=profile_text,
                source_sample=tweet_text[:20000] if len(tweet_text) > 20000 else tweet_text,
            )
            db.add(profile)
        await db.commit()
        await db.refresh(profile)
        return _profile_to_response(profile)  # type: ignore[return-value]
    return PersonalityResponse(
        profile_text=profile_text,
        source_sample=None,
        updated_at=None,
    )
