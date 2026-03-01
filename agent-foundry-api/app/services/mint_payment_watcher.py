"""Mint payment watcher: fetch MintPaymentReceived events and trigger mints."""
from __future__ import annotations

import logging
from typing import Any

import httpx
from web3 import Web3

from app.core.config import settings

logger = logging.getLogger(__name__)

# topic0 = keccak256("MintPaymentReceived(address,address,uint256)")
MINT_PAYMENT_RECEIVED_TOPIC = "0x" + Web3.keccak(text="MintPaymentReceived(address,address,uint256)").hex()


async def estimate_required_mint_fee(
    rpc_url: str,
    gas_limit: int | None = None,
    margin_factor: float | None = None,
) -> int:
    """Estimate required AVAX wei for mint = gas_limit * gas_price * margin_factor."""
    from app.services.signer import get_gas_price

    gas_limit = gas_limit or settings.MINT_ESTIMATED_GAS
    margin_factor = margin_factor or settings.MINT_FEE_MARGIN_FACTOR
    gas_price = await get_gas_price(rpc_url)
    return int(gas_limit * gas_price * margin_factor)


async def fetch_mint_payment_events(
    rpc_url: str,
    contract_address: str,
    from_block: str | int,
    to_block: str | int = "latest",
) -> list[dict[str, Any]]:
    """Fetch MintPaymentReceived logs using eth_getLogs."""
    addr = contract_address.lower() if contract_address.startswith("0x") else contract_address
    from_b = hex(from_block) if isinstance(from_block, int) else from_block
    to_b = hex(to_block) if isinstance(to_block, int) else to_block
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_getLogs",
        "params": [
            {
                "address": addr,
                "topics": [MINT_PAYMENT_RECEIVED_TOPIC],
                "fromBlock": from_b,
                "toBlock": to_b,
            }
        ],
    }
    async with httpx.AsyncClient(timeout=settings.ACTIONS_HTTP_TIMEOUT_SEC) as client:
        resp = await client.post(rpc_url, json=payload)
        resp.raise_for_status()
        data = resp.json()
    result = data.get("result")
    return result if isinstance(result, list) else []


def parse_recipient_from_event(log: dict[str, Any]) -> str | None:
    """Extract recipient address from MintPaymentReceived log. topics[2] = recipient (indexed)."""
    topics = log.get("topics") or []
    if len(topics) < 3:
        return None
    # topics[0] = topic0, topics[1] = payer, topics[2] = recipient (32 bytes, last 20 = address)
    recipient_hex = topics[2]
    if isinstance(recipient_hex, str) and len(recipient_hex) >= 66:
        h = recipient_hex[2:] if recipient_hex.startswith("0x") else recipient_hex
        return "0x" + h[-40:].lower()
    return None


def process_mint_payments_for_network(network: str) -> dict[str, Any]:
    """
    Sync function for Celery: fetch MintPaymentReceived events, lookup intents, mint NFTs.
    Returns {processed: int, minted: int, errors: list}.
    """
    import asyncio
    return asyncio.run(_process_mint_payments_for_network_async(network))


async def _process_mint_payments_for_network_async(network: str) -> dict[str, Any]:
    """Process mint payments for a network. Uses async DB session."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from app.core.config import settings
    from app.db.base import SyncSessionLocal
    from app.models.agent_nft_contract import AgentNftContract
    from app.models.agent_wallet import AgentWallet
    from app.models.mint_payment_intent import MintPaymentIntent
    from app.models.mint_payment_watcher_state import MintPaymentWatcherState
    from app.services.signer import (
        build_and_sign_transaction,
        broadcast_raw_transaction,
        get_gas_price,
        get_transaction_count,
    )

    payment_contract = (
        settings.MINT_PAYMENT_CONTRACT_FUJI if network == "fuji" else settings.MINT_PAYMENT_CONTRACT_AVALANCHE
    )
    rpc_url = settings.AVALANCHE_FUJI_RPC_URL if network == "fuji" else settings.AVALANCHE_RPC_URL
    minter_key = settings.AGENT_NFT_MINTER_PRIVATE_KEY.strip()
    if minter_key and not minter_key.startswith("0x"):
        minter_key = "0x" + minter_key

    if not payment_contract or not rpc_url or not minter_key:
        logger.debug("mint_payment_watcher: missing config for network=%s", network)
        return {"processed": 0, "minted": 0, "errors": []}

    db = SyncSessionLocal()
    try:
        state_row = db.execute(
            select(MintPaymentWatcherState).where(MintPaymentWatcherState.network == network)
        ).scalars().one_or_none()
        from_block = (state_row.last_block_number + 1) if state_row else 0

        # Get latest block
        import httpx
        payload = {"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []}
        async with httpx.AsyncClient(timeout=settings.ACTIONS_HTTP_TIMEOUT_SEC) as http_client:
            resp = await http_client.post(rpc_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        to_block_hex = data.get("result", "0x0")
        to_block = int(to_block_hex, 16)

        if from_block > to_block:
            return {"processed": 0, "minted": 0, "errors": []}

        logs = await fetch_mint_payment_events(rpc_url, payment_contract, from_block, to_block)
        nft_row = db.execute(
            select(AgentNftContract).where(AgentNftContract.network == network)
        ).scalars().one_or_none()
        if not nft_row:
            if logs:
                logger.warning("mint_payment_watcher: no NFT contract for network=%s", network)
            if state_row:
                state_row.last_block_number = to_block
            else:
                db.add(MintPaymentWatcherState(network=network, last_block_number=to_block))
            db.commit()
            return {"processed": len(logs), "minted": 0, "errors": ["no NFT contract"]}

        nft_contract_address = nft_row.contract_address
        chain_id = 43113 if network == "fuji" else 43114
        minted_count = 0
        errors: list[str] = []

        for log in logs:
            recipient = parse_recipient_from_event(log)
            tx_hash = log.get("transactionHash")
            if not recipient or not tx_hash:
                continue

            intent = db.execute(
                select(MintPaymentIntent).where(
                    MintPaymentIntent.recipient_address == recipient,
                    MintPaymentIntent.network == network,
                    MintPaymentIntent.status == "pending_payment",
                )
            ).scalars().one_or_none()

            if not intent:
                continue

            wallet = db.execute(select(AgentWallet).where(AgentWallet.id == intent.wallet_id)).scalars().one_or_none()
            if not wallet or wallet.nft_contract:
                intent.status = "minted" if wallet and wallet.nft_contract else "failed"
                intent.payment_tx_hash = tx_hash
                continue

            # Build mint calldata: mint(address)
            from eth_abi import encode as abi_encode
            from eth_account import Account

            selector = Web3.keccak(text="mint(address)")[:4]
            encoded_addr = abi_encode(["address"], [recipient])
            data_hex = "0x" + selector.hex() + encoded_addr.hex()
            minter_account = Account.from_key(minter_key)
            from_addr = minter_account.address

            try:
                gas_price = await get_gas_price(rpc_url)
                nonce = await get_transaction_count(rpc_url, from_addr)
                signed = build_and_sign_transaction(
                    chain_id=chain_id,
                    from_address=from_addr,
                    to_address=nft_contract_address,
                    value_wei=0,
                    data_hex=data_hex,
                    gas_limit=settings.MINT_ESTIMATED_GAS,
                    gas_price_wei=gas_price,
                    nonce=nonce,
                    private_key=minter_key,
                )
                receipt = await broadcast_raw_transaction(rpc_url, signed)
                if receipt.get("ok") and receipt.get("tx_hash"):
                    mint_tx = receipt["tx_hash"]
                    intent.status = "minted"
                    intent.payment_tx_hash = tx_hash
                    intent.mint_tx_hash = mint_tx
                    wallet.nft_contract = nft_contract_address
                    # tokenId: we'd need to parse from Transfer event; use placeholder for now
                    wallet.nft_token_id = "pending"
                    minted_count += 1
                else:
                    intent.status = "failed"
                    intent.payment_tx_hash = tx_hash
                    errors.append(receipt.get("error", "mint broadcast failed"))
            except Exception as e:
                intent.status = "failed"
                intent.payment_tx_hash = tx_hash
                errors.append(str(e))
                logger.exception("mint_payment_watcher: mint failed for recipient=%s", recipient)

        if state_row:
            state_row.last_block_number = to_block
        else:
            db.add(MintPaymentWatcherState(network=network, last_block_number=to_block))
        db.commit()
        return {"processed": len(logs), "minted": minted_count, "errors": errors}
    finally:
        db.close()
