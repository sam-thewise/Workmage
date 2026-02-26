"""Purchases endpoints."""
from sqlalchemy.orm import selectinload

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.commission import platform_fee_cents
from app.core.config import settings
from app.db.session import get_db
from app.models.agent import Agent
from app.models.purchase import Purchase
from app.models.subscription import Subscription
from app.models.user import User, ExpertProfile
from pydantic import BaseModel

from app.schemas.purchase import CheckoutResponse, PurchaseCreate, PurchaseResponse

router = APIRouter(prefix="/purchases", tags=["purchases"])


class ConfirmStripeBody(BaseModel):
    session_id: str
    agent_id: int


def _get_stripe_checkout_url(
    agent: Agent,
    expert_stripe_account_id: str,
    buyer_id: int,
    success_url: str,
    cancel_url: str,
) -> str | None:
    """Create Stripe Checkout session with Connect (20% platform, 80% creator)."""
    if not settings.STRIPE_SECRET_KEY:
        return None
    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        platform_fee = platform_fee_cents(agent.price_cents)
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": agent.name, "description": agent.description or ""},
                    "unit_amount": agent.price_cents,
                },
                "quantity": 1,
            }],
            success_url=f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}&agent_id={agent.id}",
            cancel_url=cancel_url,
            metadata={"agent_id": str(agent.id), "buyer_id": str(buyer_id)},
            payment_intent_data={
                "application_fee_amount": platform_fee,
                "transfer_data": {"destination": expert_stripe_account_id},
            },
        )
        return session.url
    except Exception:
        return None


@router.get("/my")
async def list_my_purchases(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List current user's purchases with agent names."""
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Purchase)
        .options(selectinload(Purchase.agent))
        .where(Purchase.buyer_id == user.id)
        .order_by(Purchase.purchased_at.desc())
    )
    purchases = result.scalars().all()
    return [
        {
            "id": p.id,
            "agent_id": p.agent_id,
            "agent_name": p.agent.name if p.agent else None,
            "purchased_at": p.purchased_at,
        }
        for p in purchases
    ]


@router.post("/", response_model=CheckoutResponse)
async def create_purchase(
    payload: PurchaseCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Purchase an agent. Free agents: direct. Paid: Stripe Checkout URL (requires expert Stripe Connect)."""
    result = await db.execute(
        select(Agent)
        .options(selectinload(Agent.expert).selectinload(User.expert_profile))
        .where(Agent.id == payload.agent_id, Agent.status == "listed")
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found or not listed")
    if agent.price_cents > 0:
        expert_profile = agent.expert.expert_profile if agent.expert else None
        stripe_account = (
            (expert_profile.stripe_connect_account_id if expert_profile else None)
            or None
        )
        if not stripe_account:
            raise HTTPException(
                400,
                "This agent cannot be purchased yet. The creator must link their Stripe account first.",
            )
    # Check already purchased
    existing = await db.execute(
        select(Purchase).where(
            Purchase.buyer_id == user.id,
            Purchase.agent_id == payload.agent_id,
        )
    )
    if existing.scalar_one_or_none():
        return CheckoutResponse(success=True, message="Already purchased")
    # Ensure buyer has subscription for platform runs
    from app.models.subscription import Subscription
    sub_check = await db.execute(select(Subscription).where(Subscription.buyer_id == user.id))
    if not sub_check.scalar_one_or_none():
        db.add(Subscription(buyer_id=user.id, tier="free", runs_per_period=5, period="monthly"))
        await db.commit()

    # Free agent: record directly
    if agent.price_cents == 0:
        purchase = Purchase(buyer_id=user.id, agent_id=agent.id)
        db.add(purchase)
        await db.commit()
        await db.refresh(purchase)
        return CheckoutResponse(success=True, purchase_id=purchase.id)
    # Paid: Stripe Checkout with Connect (stripe_account verified above)
    success_url = f"{settings.FRONTEND_URL}/purchase/success"
    cancel_url = f"{settings.FRONTEND_URL}/agents/{agent.id}"
    checkout_url = _get_stripe_checkout_url(
        agent, stripe_account, user.id, success_url, cancel_url
    )
    if not checkout_url:
        raise HTTPException(
            503,
            "Stripe is not configured. Set STRIPE_SECRET_KEY for paid agents.",
        )
    return CheckoutResponse(success=True, checkout_url=checkout_url)


@router.post("/confirm-stripe")
async def confirm_stripe_purchase(
    body: ConfirmStripeBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm purchase after Stripe redirect. Verifies session and records purchase."""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(503, "Stripe not configured")
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        session = stripe.checkout.Session.retrieve(body.session_id)
    except Exception:
        raise HTTPException(400, "Invalid session")
    if session.payment_status != "paid":
        raise HTTPException(400, "Payment not completed")
    aid = int(session.metadata.get("agent_id", 0))
    if aid != body.agent_id:
        raise HTTPException(400, "Agent mismatch")
    existing = await db.execute(
        select(Purchase).where(
            Purchase.buyer_id == user.id,
            Purchase.agent_id == body.agent_id,
        )
    )
    if existing.scalar_one_or_none():
        return {"success": True, "message": "Already recorded"}
    purchase = Purchase(buyer_id=user.id, agent_id=body.agent_id)
    db.add(purchase)
    await db.commit()
    await db.refresh(purchase)
    return {"success": True, "purchase_id": purchase.id}


@router.get("/check/{agent_id}")
async def check_purchase(
    agent_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check if user has purchased this agent."""
    result = await db.execute(
        select(Purchase).where(
            Purchase.buyer_id == user.id,
            Purchase.agent_id == agent_id,
        )
    )
    purchased = result.scalar_one_or_none() is not None
    return {"purchased": purchased}
