"""Stripe webhook endpoint - receives checkout.session.completed and records purchase."""
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.api.v1.endpoints.purchases import _create_chain_transfers, _get_chain_owner_payouts
from app.core.config import settings
from app.db.base import AsyncSessionLocal
from app.models.chain import AgentChain
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
        metadata = session.get("metadata", {}) or {}
        item_type = metadata.get("item_type") or ("chain" if metadata.get("chain_id") else "agent")
        buyer_id = int(metadata.get("buyer_id", 0))
        if not buyer_id:
            return {"received": True}
        async with AsyncSessionLocal() as db:
            if item_type == "chain":
                chain_id = int(metadata.get("chain_id", 0))
                if not chain_id:
                    return {"received": True}
                existing = await db.execute(
                    select(Purchase).where(
                        Purchase.buyer_id == buyer_id,
                        Purchase.chain_id == chain_id,
                    )
                )
                if existing.scalar_one_or_none():
                    return {"received": True}
                chain_result = await db.execute(select(AgentChain).where(AgentChain.id == chain_id))
                chain = chain_result.scalar_one_or_none()
                if not chain:
                    return {"received": True}
                payouts = await _get_chain_owner_payouts(db, chain)
                transfer_group = metadata.get("transfer_group") or f"chain_{chain_id}_{buyer_id}"
                transfer_ids = _create_chain_transfers(stripe, session, transfer_group, payouts)
                db.add(
                    Purchase(
                        buyer_id=buyer_id,
                        chain_id=chain_id,
                        payout_plan={
                            "splits": payouts,
                            "transfer_ids": transfer_ids,
                            "transfer_group": transfer_group,
                        },
                    )
                )
            else:
                agent_id = int(metadata.get("agent_id", 0))
                if not agent_id:
                    return {"received": True}
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
