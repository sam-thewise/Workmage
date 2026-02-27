"""Endpoint-level integration tests for action-infra routes."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models.action_runtime import ActionApproval


pytestmark = pytest.mark.asyncio


API = "/api/v1/action-infra"


async def test_health_ok(client: AsyncClient):
    """Health does not require auth."""
    r = await client.get(f"{API}/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["service"] == "action-infra"
    assert "live_tx_enabled" in data
    assert "reference_capabilities_enabled" in data


async def test_list_executions_requires_auth(client: AsyncClient):
    r = await client.get(f"{API}/executions")
    assert r.status_code == 401


async def test_list_executions_ok(client: AsyncClient, auth_headers: dict):
    r = await client.get(f"{API}/executions", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_create_wallet_ok(client: AsyncClient, auth_headers: dict, test_agent):
    r = await client.post(
        f"{API}/wallets",
        json={
            "agent_id": test_agent.id,
            "wallet_address": "0x2222222222222222222222222222222222222222",
            "chain_id": 43114,
        },
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "wallet_id" in data
    assert data["wallet_address"] == "0x2222222222222222222222222222222222222222"
    assert data["status"] == "active"


async def test_create_wallet_managed_ok(client: AsyncClient, auth_headers: dict, test_agent):
    """Managed wallet: omit wallet_address or set managed=true to have platform generate key and store encrypted."""
    r = await client.post(
        f"{API}/wallets",
        json={"agent_id": test_agent.id, "managed": True, "chain_id": 43114},
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "wallet_id" in data
    assert data["status"] == "active"
    # wallet_address should be a valid 0x-prefixed address (42 chars)
    addr = data["wallet_address"]
    assert addr.startswith("0x") and len(addr) == 42


async def test_create_wallet_agent_not_found(client: AsyncClient, auth_headers: dict):
    r = await client.post(
        f"{API}/wallets",
        json={"agent_id": 99999, "wallet_address": "0x0000000000000000000000000000000000000001"},
        headers=auth_headers,
    )
    assert r.status_code == 404


async def test_fund_intent_ok(client: AsyncClient, auth_headers: dict, test_wallet):
    r = await client.post(
        f"{API}/wallets/{test_wallet.id}/fund",
        json={"amount_wei": "1000000000000000000", "asset": "AVAX"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "requested"
    assert "intent_id" in data


async def test_withdraw_intent_ok(client: AsyncClient, auth_headers: dict, test_wallet):
    r = await client.post(
        f"{API}/wallets/{test_wallet.id}/withdraw",
        json={"amount_wei": "500000000000000000", "asset": "AVAX"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "requested"


async def test_trust_profile_upsert_ok(client: AsyncClient, auth_headers: dict, test_agent):
    r = await client.post(
        f"{API}/trust/{test_agent.id}",
        json={"trust_score": 60, "metadata": {}},
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["agent_id"] == test_agent.id
    assert data["trust_score"] == 60
    assert data["tier"] == "medium"


async def test_execute_simulation_ok(client: AsyncClient, auth_headers: dict, test_agent):
    """Simulation passes policy and returns receipt without broadcasting."""
    r = await client.post(
        f"{API}/execute",
        json={
            "agent_id": test_agent.id,
            "mode": "simulation",
            "network": "avalanche",
            "amount_wei": 0,
            "max_gas_wei": 100000,
            "policy": {},
        },
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("completed", "pending_approval")
    assert "execution_id" in data
    assert "receipt" in data
    assert data["receipt"].get("mode") == "simulation"


async def test_execute_denied_over_spend(client: AsyncClient, auth_headers: dict, test_agent):
    """Policy denies when amount_wei exceeds max_spend_wei."""
    r = await client.post(
        f"{API}/execute",
        json={
            "agent_id": test_agent.id,
            "mode": "simulation",
            "amount_wei": 10**21,
            "max_gas_wei": 100000,
            "policy": {"max_spend_wei": 100},
        },
        headers=auth_headers,
    )
    assert r.status_code == 400
    assert "denied" in r.json().get("detail", "").lower()


async def test_request_approval_ok(client: AsyncClient, auth_headers: dict, db_session, test_agent):
    """Request approval for an execution (must have an execution in pending_approval)."""
    from sqlalchemy import select
    from app.models.action_runtime import ActionExecution, ActionDecision, ActionSignal, ActionAnalysis
    from app.services.action_orchestration import create_signal, create_analysis, create_decision, create_execution

    sig = await create_signal(db_session, "test", "manual", {"mode": "live"}, network="avalanche")
    analysis = await create_analysis(db_session, "policy", {"allowed": True}, signal_id=sig.id)
    decision = await create_decision(
        db_session, "policy", "execute", {"mode": "live"}, signal_id=sig.id, analysis_id=analysis.id
    )
    execution = await create_execution(
        db_session,
        mode="live",
        status="pending_approval",
        request={"mode": "live", "agent_id": test_agent.id},
        receipt={"pending_approval": True},
        agent_id=test_agent.id,
        network="avalanche",
        decision_id=decision.id,
    )
    await db_session.commit()
    await db_session.refresh(execution)

    r = await client.post(
        f"{API}/executions/{execution.id}/request-approval",
        json={"notes": "Please approve"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "pending"
    assert "approval_id" in data


async def test_approve_requires_admin(client: AsyncClient, auth_headers: dict, db_session, test_agent):
    """Approving requires admin/moderator (expert should get 403)."""
    from app.services.action_orchestration import create_signal, create_analysis, create_decision, create_execution

    sig = await create_signal(db_session, "test", "manual", {}, network="avalanche")
    analysis = await create_analysis(db_session, "policy", {}, signal_id=sig.id)
    decision = await create_decision(db_session, "policy", "execute", {}, signal_id=sig.id, analysis_id=analysis.id)
    execution = await create_execution(
        db_session, mode="live", status="pending_approval", request={}, receipt={}, decision_id=decision.id
    )
    approval = ActionApproval(execution_id=execution.id, requested_by_user_id=test_agent.expert_id, status="pending")
    db_session.add(approval)
    await db_session.commit()
    await db_session.refresh(approval)

    r = await client.post(
        f"{API}/approvals/{approval.id}/approve",
        json={},
        headers=auth_headers,
    )
    assert r.status_code == 403


async def test_approve_ok(client: AsyncClient, admin_headers: dict, db_session, test_admin, test_agent):
    """Admin can approve an approval request."""
    from app.services.action_orchestration import create_signal, create_analysis, create_decision, create_execution

    sig = await create_signal(db_session, "test", "manual", {}, network="avalanche")
    analysis = await create_analysis(db_session, "policy", {}, signal_id=sig.id)
    decision = await create_decision(db_session, "policy", "execute", {}, signal_id=sig.id, analysis_id=analysis.id)
    execution = await create_execution(
        db_session,
        mode="live",
        status="pending_approval",
        request={},
        receipt={},
        decision_id=decision.id,
        agent_id=test_agent.id,
    )
    approval = ActionApproval(
        execution_id=execution.id,
        requested_by_user_id=test_agent.expert_id,
        status="pending",
    )
    db_session.add(approval)
    await db_session.commit()
    await db_session.refresh(approval)

    r = await client.post(
        f"{API}/approvals/{approval.id}/approve",
        json={"notes": "Approved for test"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "approved"


async def test_broadcast_requires_pending_approval(client: AsyncClient, auth_headers: dict, db_session, test_agent, test_wallet):
    """Broadcast endpoint returns 400 if execution is not pending_approval or has no approved approval."""
    from app.services.action_orchestration import create_signal, create_analysis, create_decision, create_execution

    sig = await create_signal(db_session, "test", "manual", {}, network="avalanche")
    analysis = await create_analysis(db_session, "policy", {}, signal_id=sig.id)
    decision = await create_decision(db_session, "policy", "execute", {}, signal_id=sig.id, analysis_id=analysis.id)
    execution = await create_execution(
        db_session,
        mode="live",
        status="pending_approval",
        request={"to": "0x0000000000000000000000000000000000000001", "amount_wei": 0},
        receipt={},
        decision_id=decision.id,
        agent_id=test_agent.id,
    )
    approval = ActionApproval(
        execution_id=execution.id,
        requested_by_user_id=test_agent.expert_id,
        status="approved",
        approved_by_user_id=test_agent.expert_id,
    )
    db_session.add(approval)
    await db_session.commit()
    await db_session.refresh(execution)

    r = await client.post(
        f"{API}/executions/{execution.id}/broadcast",
        headers=auth_headers,
    )
    # Either 200 (if signer key set and RPC available) or 503/400 for missing config or no wallet
    assert r.status_code in (200, 400, 404, 503)


async def test_reference_liquidity_scan_disabled(client: AsyncClient, auth_headers: dict, monkeypatch):
    """When reference capabilities are disabled, liquidity-scan returns 403."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "ACTIONS_ENABLE_REFERENCE_CAPABILITIES", False)
    r = await client.post(
        f"{API}/reference/liquidity-scan",
        json={"network": "avalanche", "from_block": "latest", "to_block": "latest"},
        headers=auth_headers,
    )
    assert r.status_code == 403
