"""Purchases endpoints."""
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.commission import creator_receive_cents, platform_fee_cents
from app.core.config import settings
from app.db.session import get_db
from app.models.agent import Agent, AgentStatus
from app.models.chain import AgentChain, ChainStatus
from app.models.purchase import Purchase
from app.models.subscription import Subscription
from app.models.user import ExpertProfile, User
from app.schemas.purchase import CheckoutResponse, PurchaseCreate

router = APIRouter(prefix="/purchases", tags=["purchases"])


class ConfirmStripeBody(BaseModel):
    session_id: str
    agent_id: int | None = None
    chain_id: int | None = None


def _split_amount_evenly(total_cents: int, owner_ids: list[int]) -> dict[int, int]:
    """Split cents deterministically and keep sum exact."""
    if not owner_ids:
        return {}
    sorted_ids = sorted(owner_ids)
    base = total_cents // len(sorted_ids)
    remainder = total_cents % len(sorted_ids)
    out: dict[int, int] = {}
    for idx, owner_id in enumerate(sorted_ids):
        out[owner_id] = base + (1 if idx < remainder else 0)
    return out


async def _ensure_buyer_subscription(db: AsyncSession, buyer_id: int) -> None:
    sub_check = await db.execute(select(Subscription).where(Subscription.buyer_id == buyer_id))
    if not sub_check.scalar_one_or_none():
        db.add(Subscription(buyer_id=buyer_id, tier="free", runs_per_period=5, period="monthly"))
        await db.commit()


async def _get_chain_owner_payouts(
    db: AsyncSession,
    chain: AgentChain,
) -> list[dict]:
    """Build payout split for a chain purchase across included agent owners."""
    agent_ids = list(
        {n.get("agent_id") for n in (chain.definition or {}).get("nodes", []) if n.get("agent_id") is not None}
    )
    if not agent_ids:
        raise HTTPException(400, "Chain has no agents")
    agents_result = await db.execute(select(Agent).where(Agent.id.in_(agent_ids)))
    owners = {a.expert_id for a in agents_result.scalars().all() if a.expert_id is not None}
    if not owners:
        raise HTTPException(400, "Chain has no valid expert owners")

    profiles_result = await db.execute(
        select(ExpertProfile).where(ExpertProfile.user_id.in_(list(owners)))
    )
    profiles = {p.user_id: p for p in profiles_result.scalars().all()}

    owner_amounts = _split_amount_evenly(creator_receive_cents(chain.price_cents), list(owners))
    payouts = []
    for owner_id in sorted(owners):
        profile = profiles.get(owner_id)
        stripe_account = profile.stripe_connect_account_id if profile else None
        payouts.append(
            {
                "expert_id": owner_id,
                "stripe_account_id": stripe_account,
                "amount_cents": owner_amounts.get(owner_id, 0),
            }
        )
    return payouts


def _create_checkout_for_agent(
    agent: Agent,
    expert_stripe_account_id: str,
    buyer_id: int,
    success_url: str,
    cancel_url: str,
) -> str | None:
    """Create Stripe Checkout session for agent purchase."""
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
            metadata={
                "item_type": "agent",
                "agent_id": str(agent.id),
                "buyer_id": str(buyer_id),
            },
            payment_intent_data={
                "application_fee_amount": platform_fee,
                "transfer_data": {"destination": expert_stripe_account_id},
            },
        )
        return session.url
    except Exception:
        return None


def _create_checkout_for_chain(
    chain: AgentChain,
    buyer_id: int,
    success_url: str,
    cancel_url: str,
    transfer_group: str,
) -> str | None:
    """Create Stripe Checkout session for chain purchase."""
    if not settings.STRIPE_SECRET_KEY:
        return None
    try:
        import stripe

        stripe.api_key = settings.STRIPE_SECRET_KEY
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": chain.name, "description": chain.description or ""},
                    "unit_amount": chain.price_cents,
                },
                "quantity": 1,
            }],
            success_url=f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}&chain_id={chain.id}",
            cancel_url=cancel_url,
            metadata={
                "item_type": "chain",
                "chain_id": str(chain.id),
                "buyer_id": str(buyer_id),
                "transfer_group": transfer_group,
            },
            payment_intent_data={"transfer_group": transfer_group},
        )
        return session.url
    except Exception:
        return None


def _create_chain_transfers(
    stripe_module,
    session,
    transfer_group: str,
    payout_plan: list[dict],
) -> list[str]:
    """Create Stripe transfers for chain payouts."""
    if not session.get("payment_intent"):
        return []
    pi = stripe_module.PaymentIntent.retrieve(session["payment_intent"], expand=["latest_charge"])
    charge = pi.get("latest_charge")
    charge_id = charge.get("id") if isinstance(charge, dict) else getattr(charge, "id", None)
    if not charge_id:
        return []
    transfer_ids = []
    for split in payout_plan:
        if split["amount_cents"] <= 0:
            continue
        transfer = stripe_module.Transfer.create(
            amount=split["amount_cents"],
            currency="usd",
            destination=split["stripe_account_id"],
            transfer_group=transfer_group,
            source_transaction=charge_id,
        )
        transfer_ids.append(transfer.get("id"))
    return transfer_ids


@router.get("/my")
async def list_my_purchases(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List current user's purchases with item names."""
    result = await db.execute(
        select(Purchase)
        .options(selectinload(Purchase.agent), selectinload(Purchase.chain))
        .where(Purchase.buyer_id == user.id)
        .order_by(Purchase.purchased_at.desc())
    )
    purchases = result.scalars().all()
    return [
        {
            "id": p.id,
            "agent_id": p.agent_id,
            "agent_name": p.agent.name if p.agent else None,
            "chain_id": p.chain_id,
            "chain_name": p.chain.name if p.chain else None,
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
    """Purchase an agent or chain."""
    has_agent = payload.agent_id is not None
    has_chain = payload.chain_id is not None
    if has_agent == has_chain:
        raise HTTPException(400, "Provide exactly one of agent_id or chain_id")

    await _ensure_buyer_subscription(db, user.id)

    if payload.agent_id is not None:
        result = await db.execute(
            select(Agent)
            .options(selectinload(Agent.expert).selectinload(User.expert_profile))
            .where(
                Agent.id == payload.agent_id,
                Agent.status == AgentStatus.LISTED.value,
                Agent.approval_status == "approved",
            )
        )
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(404, "Agent not found or not listed")

        existing = await db.execute(
            select(Purchase).where(Purchase.buyer_id == user.id, Purchase.agent_id == payload.agent_id)
        )
        if existing.scalar_one_or_none():
            return CheckoutResponse(success=True, message="Already purchased")

        if agent.price_cents == 0:
            purchase = Purchase(buyer_id=user.id, agent_id=agent.id)
            db.add(purchase)
            await db.commit()
            await db.refresh(purchase)
            return CheckoutResponse(success=True, purchase_id=purchase.id)

        expert_profile = agent.expert.expert_profile if agent.expert else None
        stripe_account = (expert_profile.stripe_connect_account_id if expert_profile else None) or None
        if not stripe_account:
            raise HTTPException(
                400,
                "This agent cannot be purchased yet. The creator must link their Stripe account first.",
            )
        checkout_url = _create_checkout_for_agent(
            agent=agent,
            expert_stripe_account_id=stripe_account,
            buyer_id=user.id,
            success_url=f"{settings.FRONTEND_URL}/purchase/success",
            cancel_url=f"{settings.FRONTEND_URL}/agents/{agent.id}",
        )
        if not checkout_url:
            raise HTTPException(503, "Stripe is not configured. Set STRIPE_SECRET_KEY for paid items.")
        return CheckoutResponse(success=True, checkout_url=checkout_url)

    result = await db.execute(
        select(AgentChain).where(
            AgentChain.id == payload.chain_id,
            AgentChain.status == ChainStatus.LISTED.value,
            AgentChain.approval_status == "approved",
        )
    )
    chain = result.scalar_one_or_none()
    if not chain:
        raise HTTPException(404, "Chain not found or not listed")

    existing = await db.execute(
        select(Purchase).where(Purchase.buyer_id == user.id, Purchase.chain_id == payload.chain_id)
    )
    if existing.scalar_one_or_none():
        return CheckoutResponse(success=True, message="Already purchased")

    if chain.price_cents == 0:
        purchase = Purchase(buyer_id=user.id, chain_id=chain.id)
        db.add(purchase)
        await db.commit()
        await db.refresh(purchase)
        return CheckoutResponse(success=True, purchase_id=purchase.id)

    payouts = await _get_chain_owner_payouts(db, chain)
    missing_accounts = [p["expert_id"] for p in payouts if not p["stripe_account_id"]]
    if missing_accounts:
        raise HTTPException(
            400,
            "This chain cannot be purchased yet. One or more included experts have not linked Stripe.",
        )

    transfer_group = f"chain_{chain.id}_{user.id}_{uuid4().hex[:8]}"
    checkout_url = _create_checkout_for_chain(
        chain=chain,
        buyer_id=user.id,
        success_url=f"{settings.FRONTEND_URL}/purchase/success",
        cancel_url=f"{settings.FRONTEND_URL}/chains/{chain.id}",
        transfer_group=transfer_group,
    )
    if not checkout_url:
        raise HTTPException(503, "Stripe is not configured. Set STRIPE_SECRET_KEY for paid items.")
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

    metadata = session.metadata or {}
    item_type = metadata.get("item_type") or ("chain" if metadata.get("chain_id") else "agent")
    buyer_id = int(metadata.get("buyer_id", 0))
    if buyer_id and buyer_id != user.id:
        raise HTTPException(403, "Purchase does not belong to this user")

    if item_type == "chain":
        cid = int(metadata.get("chain_id", 0))
        if not cid or (body.chain_id and cid != body.chain_id):
            raise HTTPException(400, "Chain mismatch")
        existing = await db.execute(
            select(Purchase).where(Purchase.buyer_id == user.id, Purchase.chain_id == cid)
        )
        purchase = existing.scalar_one_or_none()
        if purchase:
            return {"success": True, "message": "Already recorded", "purchase_id": purchase.id}

        chain_result = await db.execute(select(AgentChain).where(AgentChain.id == cid))
        chain = chain_result.scalar_one_or_none()
        if not chain:
            raise HTTPException(404, "Chain not found")
        payouts = await _get_chain_owner_payouts(db, chain)
        transfer_group = metadata.get("transfer_group") or f"chain_{cid}_{user.id}"
        transfer_ids = _create_chain_transfers(stripe, session, transfer_group, payouts)
        payout_plan = {"splits": payouts, "transfer_ids": transfer_ids, "transfer_group": transfer_group}
        purchase = Purchase(buyer_id=user.id, chain_id=cid, payout_plan=payout_plan)
        db.add(purchase)
        await db.commit()
        await db.refresh(purchase)
        return {"success": True, "purchase_id": purchase.id}

    aid = int(metadata.get("agent_id", 0))
    if not aid or (body.agent_id and aid != body.agent_id):
        raise HTTPException(400, "Agent mismatch")
    existing = await db.execute(select(Purchase).where(Purchase.buyer_id == user.id, Purchase.agent_id == aid))
    purchase = existing.scalar_one_or_none()
    if purchase:
        return {"success": True, "message": "Already recorded", "purchase_id": purchase.id}
    purchase = Purchase(buyer_id=user.id, agent_id=aid)
    db.add(purchase)
    await db.commit()
    await db.refresh(purchase)
    return {"success": True, "purchase_id": purchase.id}


@router.get("/check")
async def check_purchase(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    agent_id: int | None = None,
    chain_id: int | None = None,
):
    """Check if user has purchased an agent or chain."""
    if (agent_id is None and chain_id is None) or (agent_id is not None and chain_id is not None):
        raise HTTPException(400, "Provide exactly one of agent_id or chain_id")
    if agent_id is not None:
        result = await db.execute(
            select(Purchase).where(Purchase.buyer_id == user.id, Purchase.agent_id == agent_id)
        )
    else:
        result = await db.execute(
            select(Purchase).where(Purchase.buyer_id == user.id, Purchase.chain_id == chain_id)
        )
    purchased = result.scalar_one_or_none() is not None
    return {"purchased": purchased}


@router.get("/check/{agent_id}")
async def check_agent_purchase_legacy(
    agent_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Backward-compatible purchase check endpoint for agents."""
    result = await db.execute(
        select(Purchase).where(Purchase.buyer_id == user.id, Purchase.agent_id == agent_id)
    )
    return {"purchased": result.scalar_one_or_none() is not None}
