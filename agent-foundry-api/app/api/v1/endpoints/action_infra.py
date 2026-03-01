"""Action infrastructure endpoints for capabilities, policy, and execution."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_or_moderator, get_current_user
from app.db.session import get_db
from app.models.action_runtime import ActionApproval, ActionExecution
from app.models.agent import Agent
from app.models.agent_wallet import AgentTrustProfile, AgentWallet, AgentWalletSignerKey, WalletFundingIntent
from app.models.mint_payment_intent import MintPaymentIntent
from app.models.purchase import Purchase
from app.models.user import User
from app.services.action_orchestration import (
    create_analysis,
    create_audit_trail,
    create_decision,
    create_execution,
    create_policy_event,
    create_signal,
)
from app.services.contract_audit import run_static_audit_checks
from app.services.contract_source import fetch_verified_source
from app.services.liquidity_watcher import default_factory_addresses, fetch_pair_created_logs
from app.services.mint_payment_watcher import estimate_required_mint_fee
from app.services.policy_engine import evaluate_action_policy
from app.services.trust_signals import normalize_trust_metadata
from app.services.tx_executor import broadcast_execution, execute_transaction

router = APIRouter(prefix="/action-infra", tags=["action-infra"])


class WalletCreateRequest(BaseModel):
    agent_id: int
    wallet_address: str | None = Field(None, min_length=1)
    chain_id: int = 43114
    nft_contract: str | None = None
    nft_token_id: str | None = None
    signer_address: str | None = None
    managed: bool = False


class FundingIntentRequest(BaseModel):
    amount_wei: str = Field(..., min_length=1)
    asset: str = "AVAX"
    notes: str | None = None


class TrustProfileRequest(BaseModel):
    identity_registry_ref: str | None = None
    reputation_registry_ref: str | None = None
    validation_registry_ref: str | None = None
    trust_score: int = 0
    metadata: dict = Field(default_factory=dict)


class ExecutionRequest(BaseModel):
    agent_id: int | None = None
    mode: str = "simulation"
    network: str = "avalanche"
    amount_wei: int = 0
    max_gas_wei: int = 0
    token_in: str | None = None
    token_out: str | None = None
    router: str | None = None
    to: str | None = None
    from_address: str | None = None
    payload: dict = Field(default_factory=dict)
    policy: dict = Field(default_factory=dict)


class LiquidityScanRequest(BaseModel):
    network: str = "avalanche"
    from_block: str = "latest"
    to_block: str = "latest"
    factory_addresses: list[str] = Field(default_factory=list)
    token_contract: str | None = None


class ApprovalRequest(BaseModel):
    notes: str | None = None


@router.get("/health")
async def get_health():
    from app.core.config import settings

    return {
        "status": "ok",
        "service": "action-infra",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "live_tx_enabled": settings.ACTIONS_ENABLE_LIVE_TX,
        "reference_capabilities_enabled": settings.ACTIONS_ENABLE_REFERENCE_CAPABILITIES,
    }


@router.get("/executions")
async def list_executions(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ActionExecution).order_by(ActionExecution.created_at.desc()).limit(min(100, max(1, limit)))
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "agent_id": r.agent_id,
            "mode": r.mode,
            "status": r.status,
            "tx_hash": r.tx_hash,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def _chain_id_to_network(chain_id: int) -> str:
    return "fuji" if chain_id == 43113 else "avalanche"


@router.get("/wallets")
async def list_my_wallets(
    agent_id: int | None = None,
    network: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List action wallets owned by the current user (for dashboard)."""
    q = select(AgentWallet, Agent.name.label("agent_name")).where(
        AgentWallet.owner_user_id == user.id,
    ).join(Agent, AgentWallet.agent_id == Agent.id)
    if agent_id is not None:
        q = q.where(AgentWallet.agent_id == agent_id)
    if network is not None:
        q = q.where(AgentWallet.network == network)
    q = q.order_by(AgentWallet.created_at.desc())
    result = await db.execute(q)
    rows = result.all()
    return [
        {
            "id": w.id,
            "agent_id": w.agent_id,
            "agent_name": name,
            "network": w.network,
            "chain_id": w.chain_id,
            "wallet_address": w.wallet_address,
            "status": w.status,
            "created_at": w.created_at.isoformat() if w.created_at else None,
        }
        for w, name in rows
    ]


@router.post("/wallets")
async def create_wallet(
    payload: WalletCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from datetime import datetime, timedelta

    from eth_account import Account

    from app.core.config import settings
    from app.core.key_encryption import encrypt_signer_key

    agent = (await db.execute(select(Agent).where(Agent.id == payload.agent_id))).scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    is_owner = agent.expert_id == user.id
    if not is_owner:
        purchase = (
            await db.execute(
                select(Purchase).where(
                    Purchase.buyer_id == user.id,
                    Purchase.agent_id == payload.agent_id,
                )
            )
        ).scalar_one_or_none()
        if not purchase:
            raise HTTPException(403, "Only the agent owner or a purchaser can create a wallet for this agent")

    network = _chain_id_to_network(payload.chain_id)
    use_managed = payload.managed or not (payload.wallet_address and payload.wallet_address.strip())
    if use_managed:
        account = Account.create()
        wallet_address = account.address
        record = AgentWallet(
            agent_id=payload.agent_id,
            owner_user_id=user.id,
            network=network,
            chain_id=payload.chain_id,
            wallet_address=wallet_address,
            nft_contract=payload.nft_contract,
            nft_token_id=payload.nft_token_id,
            signer_address=payload.signer_address,
        )
        db.add(record)
        await db.flush()
        key_row = AgentWalletSignerKey(
            wallet_id=record.id,
            encrypted_key=encrypt_signer_key(account.key.hex()),
            key_version=1,
        )
        db.add(key_row)

        payment_contract = (
            settings.MINT_PAYMENT_CONTRACT_FUJI if network == "fuji" else settings.MINT_PAYMENT_CONTRACT_AVALANCHE
        )
        rpc_url = settings.AVALANCHE_FUJI_RPC_URL if network == "fuji" else settings.AVALANCHE_RPC_URL
        if payment_contract and rpc_url:
            try:
                required_avax_wei = await estimate_required_mint_fee(rpc_url)
            except Exception:
                required_avax_wei = 200000000000000  # fallback ~0.0002 AVAX
            expires_at = datetime.utcnow() + timedelta(hours=settings.MINT_INTENT_EXPIRY_HOURS)
            recipient_normalized = wallet_address.lower()
            intent = MintPaymentIntent(
                wallet_id=record.id,
                recipient_address=recipient_normalized,
                required_avax_wei=str(required_avax_wei),
                network=network,
                status="pending_payment",
                expires_at=expires_at,
            )
            db.add(intent)
            await db.commit()
            await db.refresh(record)
            return {
                "wallet_id": record.id,
                "wallet_address": record.wallet_address,
                "status": record.status,
                "mint_payment": {
                    "payment_contract_address": payment_contract,
                    "required_avax_wei": str(required_avax_wei),
                    "payment_instructions": (
                        f"Call payForMint({record.wallet_address}) on contract {payment_contract} "
                        f"with >= {required_avax_wei} wei (AVAX) to mint your Workmage Agent NFT."
                    ),
                },
            }
    else:
        record = AgentWallet(
            agent_id=payload.agent_id,
            owner_user_id=user.id,
            network=network,
            chain_id=payload.chain_id,
            wallet_address=payload.wallet_address.strip(),
            nft_contract=payload.nft_contract,
            nft_token_id=payload.nft_token_id,
            signer_address=payload.signer_address,
        )
        db.add(record)
    await db.commit()
    await db.refresh(record)
    return {"wallet_id": record.id, "wallet_address": record.wallet_address, "status": record.status}


@router.get("/wallets/{wallet_id}/mint-status")
async def get_mint_status(
    wallet_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get mint payment intent status for a managed wallet (pending_payment | paid | minted | expired | failed)."""
    wallet = (await db.execute(select(AgentWallet).where(AgentWallet.id == wallet_id))).scalar_one_or_none()
    if not wallet:
        raise HTTPException(404, "Wallet not found")
    if wallet.owner_user_id != user.id:
        raise HTTPException(403, "Wallet ownership mismatch")
    intent = (
        await db.execute(
            select(MintPaymentIntent)
            .where(MintPaymentIntent.wallet_id == wallet_id)
            .order_by(MintPaymentIntent.created_at.desc())
            .limit(1)
        )
    ).scalars().first()
    if not intent:
        return {
            "wallet_id": wallet_id,
            "mint_status": "none",
            "nft_contract": wallet.nft_contract,
            "nft_token_id": wallet.nft_token_id,
        }
    return {
        "wallet_id": wallet_id,
        "mint_status": intent.status,
        "payment_tx_hash": intent.payment_tx_hash,
        "mint_tx_hash": intent.mint_tx_hash,
        "required_avax_wei": intent.required_avax_wei,
        "expires_at": intent.expires_at.isoformat() if intent.expires_at else None,
        "nft_contract": wallet.nft_contract,
        "nft_token_id": wallet.nft_token_id,
    }


@router.post("/wallets/{wallet_id}/fund")
async def create_funding_intent(
    wallet_id: int,
    payload: FundingIntentRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    wallet = (await db.execute(select(AgentWallet).where(AgentWallet.id == wallet_id))).scalar_one_or_none()
    if not wallet:
        raise HTTPException(404, "Wallet not found")
    if wallet.owner_user_id != user.id:
        raise HTTPException(403, "Wallet ownership mismatch")
    intent = WalletFundingIntent(
        wallet_id=wallet.id,
        user_id=user.id,
        intent_type="fund",
        amount_wei=payload.amount_wei,
        asset=payload.asset,
        notes=payload.notes,
    )
    db.add(intent)
    await db.commit()
    return {"intent_id": intent.id, "status": intent.status}


@router.post("/wallets/{wallet_id}/withdraw")
async def create_withdraw_intent(
    wallet_id: int,
    payload: FundingIntentRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    wallet = (await db.execute(select(AgentWallet).where(AgentWallet.id == wallet_id))).scalar_one_or_none()
    if not wallet:
        raise HTTPException(404, "Wallet not found")
    if wallet.owner_user_id != user.id:
        raise HTTPException(403, "Wallet ownership mismatch")
    intent = WalletFundingIntent(
        wallet_id=wallet.id,
        user_id=user.id,
        intent_type="withdraw",
        amount_wei=payload.amount_wei,
        asset=payload.asset,
        notes=payload.notes,
    )
    db.add(intent)
    await db.commit()
    return {"intent_id": intent.id, "status": intent.status}


@router.post("/trust/{agent_id}")
async def upsert_trust_profile(
    agent_id: int,
    payload: TrustProfileRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    agent = (await db.execute(select(Agent).where(Agent.id == agent_id))).scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    if agent.expert_id != user.id:
        raise HTTPException(403, "Only agent owner can update trust metadata")

    normalized = normalize_trust_metadata(payload.model_dump())
    existing = (
        await db.execute(select(AgentTrustProfile).where(AgentTrustProfile.agent_id == agent_id))
    ).scalar_one_or_none()
    if existing:
        existing.identity_registry_ref = normalized["identity_registry_ref"]
        existing.reputation_registry_ref = normalized["reputation_registry_ref"]
        existing.validation_registry_ref = normalized["validation_registry_ref"]
        existing.trust_score = normalized["trust_score"]
        existing.tier = normalized["tier"]
        existing.trust_metadata = normalized["metadata"]
        profile = existing
    else:
        profile = AgentTrustProfile(
            agent_id=agent_id,
            identity_registry_ref=normalized["identity_registry_ref"],
            reputation_registry_ref=normalized["reputation_registry_ref"],
            validation_registry_ref=normalized["validation_registry_ref"],
            trust_score=normalized["trust_score"],
            tier=normalized["tier"],
            trust_metadata=normalized["metadata"],
        )
        db.add(profile)
    await db.commit()
    return {"agent_id": agent_id, "trust_score": profile.trust_score, "tier": profile.tier}


@router.post("/execute")
async def run_execution(
    payload: ExecutionRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    trust_score = 0
    if payload.agent_id:
        profile = (
            await db.execute(select(AgentTrustProfile).where(AgentTrustProfile.agent_id == payload.agent_id))
        ).scalar_one_or_none()
        trust_score = profile.trust_score if profile else 0

    req = payload.model_dump()
    policy_result = evaluate_action_policy(payload.policy, req, trust_score=trust_score)
    signal = await create_signal(db, "api", "manual_execution", req, network=payload.network)
    analysis = await create_analysis(
        db,
        "policy_precheck",
        {"allowed": policy_result.allowed, "reason": policy_result.reason, "details": policy_result.details or {}},
        signal_id=signal.id,
    )
    decision = await create_decision(
        db,
        "policy_engine",
        "execute" if policy_result.allowed else "deny",
        req,
        signal_id=signal.id,
        analysis_id=analysis.id,
        reason=policy_result.reason,
    )
    if not policy_result.allowed:
        execution = await create_execution(
            db,
            mode=payload.mode,
            status="denied",
            request=req,
            receipt={"error": policy_result.reason},
            decision_id=decision.id,
            agent_id=payload.agent_id,
            runner_user_id=user.id,
            network=payload.network,
        )
        await create_policy_event(
            db,
            action="execute",
            outcome="deny",
            reason=policy_result.reason,
            details=policy_result.details or {},
            execution_id=execution.id,
            agent_id=payload.agent_id,
        )
        await create_audit_trail(
            db,
            actor_type="user",
            actor_id=str(user.id),
            event_type="execution_denied",
            entity_type="action_execution",
            entity_id=str(execution.id),
            payload={"reason": policy_result.reason},
        )
        await db.commit()
        raise HTTPException(400, f"Execution denied: {policy_result.reason}")

    receipt = await execute_transaction(req)
    status = "completed" if receipt.get("ok") else "error"
    if payload.mode == "live" and receipt.get("pending_approval"):
        status = "pending_approval"
    execution = await create_execution(
        db,
        mode=payload.mode,
        status=status,
        request=req,
        receipt=receipt,
        decision_id=decision.id,
        agent_id=payload.agent_id,
        runner_user_id=user.id,
        network=payload.network,
        tx_hash=receipt.get("tx_hash"),
    )
    await create_policy_event(
        db,
        action="execute",
        outcome="allow",
        reason="policy_pass",
        execution_id=execution.id,
        agent_id=payload.agent_id,
    )
    await create_audit_trail(
        db,
        actor_type="user",
        actor_id=str(user.id),
        event_type="execution_attempt",
        entity_type="action_execution",
        entity_id=str(execution.id),
        payload={"mode": payload.mode, "status": status},
    )
    await db.commit()
    return {"execution_id": execution.id, "status": execution.status, "receipt": receipt}


@router.post("/executions/{execution_id}/request-approval")
async def request_live_approval(
    execution_id: int,
    payload: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    execution = (await db.execute(select(ActionExecution).where(ActionExecution.id == execution_id))).scalar_one_or_none()
    if not execution:
        raise HTTPException(404, "Execution not found")
    approval = ActionApproval(
        execution_id=execution.id,
        requested_by_user_id=user.id,
        notes=payload.notes,
        status="pending",
    )
    db.add(approval)
    await create_audit_trail(
        db,
        actor_type="user",
        actor_id=str(user.id),
        event_type="execution_approval_requested",
        entity_type="action_execution",
        entity_id=str(execution.id),
        payload={"notes": payload.notes},
    )
    await db.commit()
    return {"approval_id": approval.id, "status": approval.status}


@router.post("/approvals/{approval_id}/approve")
async def approve_execution(
    approval_id: int,
    payload: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_admin_or_moderator),
):
    approval = (await db.execute(select(ActionApproval).where(ActionApproval.id == approval_id))).scalar_one_or_none()
    if not approval:
        raise HTTPException(404, "Approval not found")
    approval.status = "approved"
    approval.notes = payload.notes or approval.notes
    approval.approved_by_user_id = user.id
    approval.decided_at = datetime.utcnow()
    await create_audit_trail(
        db,
        actor_type="moderator",
        actor_id=str(user.id),
        event_type="execution_approved",
        entity_type="action_approval",
        entity_id=str(approval.id),
        payload={"execution_id": approval.execution_id},
    )
    await db.commit()
    return {"approval_id": approval.id, "status": approval.status}


@router.post("/executions/{execution_id}/broadcast")
async def broadcast_live_execution(
    execution_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """After approval, build/sign/broadcast the transaction for a pending_approval execution."""
    from app.core.config import settings

    execution = (await db.execute(select(ActionExecution).where(ActionExecution.id == execution_id))).scalar_one_or_none()
    if not execution:
        raise HTTPException(404, "Execution not found")
    if execution.mode != "live":
        raise HTTPException(400, "Execution is not a live execution")
    if execution.status != "pending_approval":
        raise HTTPException(400, f"Execution status is {execution.status}; only pending_approval can be broadcast")
    approval = (
        await db.execute(
            select(ActionApproval).where(
                ActionApproval.execution_id == execution_id,
                ActionApproval.status == "approved",
            )
        )
    ).scalar_one_or_none()
    if not approval:
        raise HTTPException(400, "No approved approval for this execution")
    if execution.runner_user_id is not None and execution.runner_user_id != user.id:
        raise HTTPException(403, "Only the runner who initiated this execution can broadcast it")
    if not execution.agent_id:
        raise HTTPException(400, "Execution has no agent_id; cannot resolve wallet")
    runner_id = execution.runner_user_id or user.id
    wallet = (
        await db.execute(
            select(AgentWallet).where(
                AgentWallet.agent_id == execution.agent_id,
                AgentWallet.owner_user_id == runner_id,
                AgentWallet.network == execution.network,
                AgentWallet.status == "active",
            )
        )
    ).scalar_one_or_none()
    if not wallet:
        raise HTTPException(
            404,
            "No active wallet for this agent on this network for your account. Create one from My action wallets.",
        )
    rpc_url = settings.AVALANCHE_FUJI_RPC_URL if execution.network == "fuji" else settings.AVALANCHE_RPC_URL
    if not rpc_url:
        raise HTTPException(503, "RPC URL not configured for this network")
    chain_id = 43113 if execution.network == "fuji" else 43114
    req = execution.request or {}
    req.setdefault("from_address", wallet.wallet_address)
    receipt = await broadcast_execution(db, rpc_url, chain_id, wallet.wallet_address, req)
    execution.receipt = {**execution.receipt, "broadcast": receipt}
    execution.tx_hash = receipt.get("tx_hash")
    execution.status = "completed" if receipt.get("ok") else "error"
    execution.updated_at = datetime.utcnow()
    await create_audit_trail(
        db,
        actor_type="user",
        actor_id=str(user.id),
        event_type="execution_broadcast",
        entity_type="action_execution",
        entity_id=str(execution.id),
        payload={"tx_hash": execution.tx_hash, "ok": receipt.get("ok")},
    )
    await db.commit()
    return {"execution_id": execution.id, "status": execution.status, "tx_hash": execution.tx_hash, "receipt": receipt}


@router.post("/reference/liquidity-scan")
async def run_reference_liquidity_scan(
    payload: LiquidityScanRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.core.config import settings  # local import to avoid circulars during tests
    if not settings.ACTIONS_ENABLE_REFERENCE_CAPABILITIES:
        raise HTTPException(403, "Reference capabilities are disabled")

    rpc_url = settings.AVALANCHE_FUJI_RPC_URL if payload.network == "fuji" else settings.AVALANCHE_RPC_URL
    if not rpc_url:
        raise HTTPException(400, f"Missing RPC URL for network `{payload.network}`")

    factories = payload.factory_addresses or default_factory_addresses()
    if not factories:
        raise HTTPException(400, "No factory addresses configured")

    logs = await fetch_pair_created_logs(
        rpc_url=rpc_url,
        factory_addresses=factories,
        from_block=payload.from_block,
        to_block=payload.to_block,
    )
    signal = await create_signal(
        db,
        source="reference_liquidity_watcher",
        signal_type="pair_created",
        payload={"network": payload.network, "log_count": len(logs)},
        network=payload.network,
    )
    source_payload = None
    audit_result = None
    if payload.token_contract:
        source_payload = await fetch_verified_source(payload.token_contract)
        audit_result = run_static_audit_checks(source_payload)
        await create_analysis(
            db,
            analyzer="reference_contract_audit",
            signal_id=signal.id,
            result={"source": source_payload, "audit": audit_result},
            summary="Reference source-fetch + deterministic audit",
        )
    await create_audit_trail(
        db,
        actor_type="user",
        actor_id=str(user.id),
        event_type="reference_liquidity_scan",
        entity_type="action_signal",
        entity_id=str(signal.id),
        payload={"log_count": len(logs), "network": payload.network},
    )
    await db.commit()
    return {
        "signal_id": signal.id,
        "network": payload.network,
        "logs_found": len(logs),
        "logs": logs[:20],
        "source": source_payload,
        "audit": audit_result,
    }
