"""Expert-specific endpoints (Stripe Connect, commission, etc.)."""
from fastapi import APIRouter, Depends, HTTPException

from app.core.commission import CREATOR_FEE_PERCENT, PLATFORM_FEE_PERCENT
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User, ExpertProfile

router = APIRouter(prefix="/experts", tags=["experts"])


async def _get_or_create_expert_profile(db: AsyncSession, user: User) -> ExpertProfile:
    """Get or create ExpertProfile for expert user."""
    result = await db.execute(
        select(ExpertProfile).where(ExpertProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    if profile:
        return profile
    profile = ExpertProfile(user_id=user.id)
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/commission")
async def get_commission():
    """Public: platform takes 20%, creator receives 80%."""
    return {
        "platform_percent": PLATFORM_FEE_PERCENT,
        "creator_percent": CREATOR_FEE_PERCENT,
    }


@router.get("/stripe-connect/status")
async def stripe_connect_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check if expert has linked Stripe. Returns linked=true/false."""
    if user.role.value != "expert":
        raise HTTPException(403, "Experts only")
    result = await db.execute(
        select(ExpertProfile).where(ExpertProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    linked = bool(profile and profile.stripe_connect_account_id)
    return {"linked": linked}


@router.get("/stripe-connect/onboard")
async def stripe_connect_onboard(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get Stripe Connect onboarding URL. Experts must complete this to sell paid agents."""
    if user.role.value != "expert":
        raise HTTPException(403, "Experts only")
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(503, "Stripe not configured")
    profile = await _get_or_create_expert_profile(db, user)
    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        if not profile.stripe_connect_account_id:
            account = stripe.Account.create(
                type="express",
                country="US",
                capabilities={
                    "card_payments": {"requested": True},
                    "transfers": {"requested": True},
                },
            )
            profile.stripe_connect_account_id = account.id
            await db.commit()
        else:
            # Existing accounts created before this change may only have card_payments requested.
            stripe.Account.modify(
                profile.stripe_connect_account_id,
                capabilities={
                    "card_payments": {"requested": True},
                    "transfers": {"requested": True},
                },
            )
        return_url = f"{settings.FRONTEND_URL}/dashboard/settings"
        refresh_url = f"{settings.FRONTEND_URL}/dashboard/settings"
        link = stripe.AccountLink.create(
            account=profile.stripe_connect_account_id,
            refresh_url=refresh_url,
            return_url=return_url,
            type="account_onboarding",
        )
        return {"url": link.url}
    except Exception as e:
        raise HTTPException(500, f"Stripe error: {str(e)}") from e
