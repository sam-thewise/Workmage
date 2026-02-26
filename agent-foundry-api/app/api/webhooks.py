"""Stripe webhook endpoint - receives checkout.session.completed and records purchase."""
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.base import AsyncSessionLocal
from app.models.purchase import Purchase

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks. Records purchase on checkout.session.completed."""
    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(503, "Stripe webhooks not configured")
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        raise HTTPException(400, f"Invalid payload: {e}") from e
    except stripe.SignatureVerificationError as e:
        raise HTTPException(400, f"Invalid signature: {e}") from e
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        agent_id = int(session.get("metadata", {}).get("agent_id", 0))
        buyer_id = int(session.get("metadata", {}).get("buyer_id", 0))
        if not agent_id or not buyer_id:
            return {"received": True}
        async with AsyncSessionLocal() as db:
            existing = await db.execute(
                select(Purchase).where(
                    Purchase.buyer_id == buyer_id,
                    Purchase.agent_id == agent_id,
                )
            )
            if existing.scalar_one_or_none():
                return {"received": True}
            db.add(Purchase(buyer_id=buyer_id, agent_id=agent_id))
            await db.commit()
    return {"received": True}
