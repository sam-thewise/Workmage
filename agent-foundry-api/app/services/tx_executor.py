"""Transaction simulation/live execution abstraction."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from app.core.config import settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _stable_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "0x" + hashlib.sha256(encoded).hexdigest()


def _rpc_url(network: str) -> str:
    if network == "fuji":
        return settings.AVALANCHE_FUJI_RPC_URL
    return settings.AVALANCHE_RPC_URL


async def execute_transaction(request: dict[str, Any]) -> dict[str, Any]:
    """Execute transaction request: simulation returns estimate; live returns pending_approval.
    Actual live broadcast is done via POST /executions/{id}/broadcast after approval.
    """
    mode = request.get("mode", "simulation")
    network = request.get("network", "avalanche")
    now = datetime.utcnow().isoformat() + "Z"
    req_hash = _stable_hash(request)

    if mode != "live":
        # Simulation: optionally call chain for gas estimate
        rpc_url = _rpc_url(network)
        raw = request.get("raw") or {}
        to_addr = raw.get("to") or request.get("to")
        value_wei = int(raw.get("value") or request.get("amount_wei") or 0)
        data_hex = raw.get("data")
        gas_limit = int(raw.get("gas_limit") or request.get("max_gas_wei") or settings.ACTIONS_DEFAULT_MAX_GAS_WEI)
        from_addr = request.get("from_address")

        if rpc_url and to_addr and from_addr:
            try:
                from app.services.signer import estimate_gas

                estimated = await estimate_gas(rpc_url, from_addr, to_addr, value_wei, data_hex)
                gas_limit = min(gas_limit, max(estimated, 21000))
            except Exception as e:
                return {
                    "ok": False,
                    "mode": "simulation",
                    "error": str(e),
                    "request_hash": req_hash,
                }
        return {
            "ok": True,
            "mode": "simulation",
            "simulated_at": now,
            "estimated_gas_wei": gas_limit,
            "request_hash": req_hash,
        }
    # Live: do not broadcast here; require approval then broadcast endpoint
    if not settings.ACTIONS_ENABLE_LIVE_TX:
        return {
            "ok": False,
            "mode": "live",
            "error": "Live transactions are disabled",
            "request_hash": req_hash,
        }
    if not _rpc_url(network):
        return {
            "ok": False,
            "mode": "live",
            "error": f"Missing RPC URL for network `{network}`",
            "request_hash": req_hash,
        }
    return {
        "ok": True,
        "mode": "live",
        "pending_approval": settings.ACTIONS_REQUIRE_APPROVAL_FOR_LIVE,
        "message": "Use POST /executions/{id}/request-approval, then POST /approvals/{id}/approve, then POST /executions/{id}/broadcast to send.",
        "request_hash": req_hash,
        "simulated_at": now,
    }


async def broadcast_execution(
    session: "AsyncSession",
    rpc_url: str,
    chain_id: int,
    wallet_address: str,
    request: dict[str, Any],
) -> dict[str, Any]:
    """Build, sign, and broadcast a transaction from execution request. Used by broadcast endpoint."""
    from app.services.signer import (
        broadcast_raw_transaction,
        build_and_sign_transaction,
        get_signer_private_key_async,
        get_gas_price,
        get_transaction_count,
    )

    key = await get_signer_private_key_async(session, wallet_address)
    if not key:
        return {"ok": False, "error": f"No signer key for wallet {wallet_address}", "tx_hash": None}

    raw = request.get("raw") or {}
    to_addr = raw.get("to") or request.get("to")
    if not to_addr:
        return {"ok": False, "error": "Missing 'to' address in request or request.raw", "tx_hash": None}
    value_wei = int(raw.get("value") or request.get("amount_wei") or 0)
    data_hex = raw.get("data")
    gas_limit = int(raw.get("gas_limit") or request.get("max_gas_wei") or settings.ACTIONS_DEFAULT_MAX_GAS_WEI)
    gas_price_wei = int(raw.get("gas_price") or request.get("gas_price_wei") or 0)
    if not gas_price_wei:
        gas_price_wei = await get_gas_price(rpc_url)
    nonce = await get_transaction_count(rpc_url, wallet_address)

    signed_hex = build_and_sign_transaction(
        chain_id=chain_id,
        from_address=wallet_address,
        to_address=to_addr,
        value_wei=value_wei,
        data_hex=data_hex,
        gas_limit=gas_limit,
        gas_price_wei=gas_price_wei,
        nonce=nonce,
        private_key=key,
    )
    return await broadcast_raw_transaction(rpc_url, signed_hex)
