"""Reference liquidity signal watcher for Avalanche-compatible DEX logs."""
from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings

# UniswapV2 PairCreated(address,address,address,uint256)
PAIR_CREATED_TOPIC = "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e9"


async def fetch_pair_created_logs(
    rpc_url: str,
    factory_addresses: list[str],
    from_block: str,
    to_block: str = "latest",
) -> list[dict[str, Any]]:
    """Fetch PairCreated logs using eth_getLogs."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_getLogs",
        "params": [
            {
                "address": factory_addresses,
                "topics": [PAIR_CREATED_TOPIC],
                "fromBlock": from_block,
                "toBlock": to_block,
            }
        ],
    }
    async with httpx.AsyncClient(timeout=settings.ACTIONS_HTTP_TIMEOUT_SEC) as client:
        response = await client.post(rpc_url, json=payload)
        response.raise_for_status()
        data = response.json()
    result = data.get("result")
    return result if isinstance(result, list) else []


def default_factory_addresses() -> list[str]:
    """Resolve factory allowlist from settings."""
    raw = settings.ACTIONS_FACTORY_ADDRESSES
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]
