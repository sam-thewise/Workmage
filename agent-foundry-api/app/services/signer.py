"""Signer and broadcast for agent wallet transactions."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.core.config import settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def get_signer_private_key(wallet_address: str) -> str | None:
    """Resolve private key for a wallet address. Keys from env only (never DB)."""
    addr = wallet_address.lower().strip()
    if not addr:
        return None
    if settings.AGENT_SIGNER_PRIVATE_KEY:
        key = settings.AGENT_SIGNER_PRIVATE_KEY.strip()
        if key.startswith("0x"):
            return key
        return "0x" + key
    if settings.AGENT_SIGNER_KEYS:
        try:
            keys = json.loads(settings.AGENT_SIGNER_KEYS)
            if isinstance(keys, dict):
                for k, v in keys.items():
                    if k and str(k).lower().strip() == addr and v:
                        key = str(v).strip()
                        return key if key.startswith("0x") else "0x" + key
        except (json.JSONDecodeError, TypeError):
            pass
    return None


async def get_signer_private_key_async(session: "AsyncSession", wallet_address: str) -> str | None:
    """Resolve private key: env first, then DB (platform-managed keys)."""
    key = get_signer_private_key(wallet_address)
    if key:
        return key
    from app.core.key_encryption import decrypt_signer_key
    from app.models.agent_wallet import AgentWallet, AgentWalletSignerKey
    from sqlalchemy import func

    addr = wallet_address.strip().lower()
    result = await session.execute(
        select(AgentWalletSignerKey)
        .join(AgentWallet, AgentWalletSignerKey.wallet_id == AgentWallet.id)
        .where(func.lower(AgentWallet.wallet_address) == addr)
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    plain = decrypt_signer_key(row.encrypted_key)
    return plain if plain.startswith("0x") else "0x" + plain


def build_and_sign_transaction(
    chain_id: int,
    from_address: str,
    to_address: str,
    value_wei: int,
    data_hex: str | None,
    gas_limit: int,
    gas_price_wei: int,
    nonce: int,
    private_key: str | None = None,
) -> str:
    """Build and sign a legacy transaction; return raw signed tx hex. If private_key is provided, use it; else resolve via get_signer_private_key(from_address)."""
    from eth_account import Account
    from eth_account.datastructures import SignedTransaction

    key = private_key or get_signer_private_key(from_address)
    if not key:
        raise ValueError(f"No signer key configured for wallet {from_address}")

    account = Account.from_key(key)
    tx = {
        "chainId": chain_id,
        "from": account.address,
        "to": to_address,
        "value": value_wei,
        "gas": gas_limit,
        "gasPrice": gas_price_wei,
        "nonce": nonce,
    }
    if data_hex:
        tx["data"] = data_hex if data_hex.startswith("0x") else "0x" + data_hex
    else:
        tx["data"] = "0x"

    signed: SignedTransaction = account.sign_transaction(tx)
    return signed.raw_transaction.hex()


async def broadcast_raw_transaction(rpc_url: str, signed_raw_hex: str) -> dict[str, Any]:
    """Send signed raw transaction via eth_sendRawTransaction."""
    import httpx

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_sendRawTransaction",
        "params": [signed_raw_hex if signed_raw_hex.startswith("0x") else "0x" + signed_raw_hex],
    }
    async with httpx.AsyncClient(timeout=settings.ACTIONS_HTTP_TIMEOUT_SEC) as client:
        response = await client.post(rpc_url, json=payload)
        response.raise_for_status()
        data = response.json()
    err = data.get("error")
    if err:
        return {"ok": False, "error": err.get("message", str(err)), "tx_hash": None}
    tx_hash = data.get("result")
    return {"ok": True, "tx_hash": tx_hash}


async def estimate_gas(rpc_url: str, from_address: str, to_address: str, value_wei: int, data_hex: str | None) -> int:
    """Call eth_estimateGas and return gas limit (or raise)."""
    import httpx

    params: dict[str, Any] = {
        "from": from_address,
        "to": to_address,
        "value": hex(value_wei),
    }
    if data_hex:
        params["data"] = data_hex if data_hex.startswith("0x") else "0x" + data_hex
    payload = {"jsonrpc": "2.0", "id": 1, "method": "eth_estimateGas", "params": [params]}
    async with httpx.AsyncClient(timeout=settings.ACTIONS_HTTP_TIMEOUT_SEC) as client:
        response = await client.post(rpc_url, json=payload)
        response.raise_for_status()
        data = response.json()
    err = data.get("error")
    if err:
        raise RuntimeError(err.get("message", str(err)))
    result = data.get("result")
    if result is None:
        raise RuntimeError("No result from eth_estimateGas")
    return int(result, 16)


async def get_transaction_count(rpc_url: str, address: str) -> int:
    """Get nonce for address via eth_getTransactionCount."""
    import httpx

    payload = {"jsonrpc": "2.0", "id": 1, "method": "eth_getTransactionCount", "params": [address, "latest"]}
    async with httpx.AsyncClient(timeout=settings.ACTIONS_HTTP_TIMEOUT_SEC) as client:
        response = await client.post(rpc_url, json=payload)
        response.raise_for_status()
        data = response.json()
    err = data.get("error")
    if err:
        raise RuntimeError(err.get("message", str(err)))
    result = data.get("result")
    if result is None:
        raise RuntimeError("No result from eth_getTransactionCount")
    return int(result, 16)


async def get_gas_price(rpc_url: str) -> int:
    """Get current gas price via eth_gasPrice."""
    import httpx

    payload = {"jsonrpc": "2.0", "id": 1, "method": "eth_gasPrice", "params": []}
    async with httpx.AsyncClient(timeout=settings.ACTIONS_HTTP_TIMEOUT_SEC) as client:
        response = await client.post(rpc_url, json=payload)
        response.raise_for_status()
        data = response.json()
    err = data.get("error")
    if err:
        raise RuntimeError(err.get("message", str(err)))
    result = data.get("result")
    if result is None:
        raise RuntimeError("No result from eth_gasPrice")
    return int(result, 16)
