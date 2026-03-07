"""Contract source retrieval service (Snowtrace/Routescan compatible)."""
from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings


def _snowtrace_base_url(network: str) -> str:
    """Return Snowtrace/Routescan API base URL for the given network."""
    if network == "fuji":
        return settings.SNOWTRACE_FUJI_API_URL.rstrip("/")
    return settings.SNOWTRACE_API_URL.rstrip("/")


async def fetch_verified_source(
    contract_address: str,
    network: str = "avalanche",
) -> dict[str, Any]:
    """Fetch verified contract source via Etherscan-compatible API.

    Args:
        contract_address: Contract address (0x...).
        network: "fuji" for Fuji testnet, "avalanche" for mainnet. Default mainnet.
    """
    endpoint = _snowtrace_base_url(network)
    params = {
        "module": "contract",
        "action": "getsourcecode",
        "address": contract_address,
    }
    if settings.SNOWTRACE_API_KEY:
        params["apikey"] = settings.SNOWTRACE_API_KEY

    async with httpx.AsyncClient(timeout=settings.ACTIONS_HTTP_TIMEOUT_SEC) as client:
        response = await client.get(endpoint, params=params)
        response.raise_for_status()
        data = response.json()

    result = data.get("result")
    if not isinstance(result, list) or not result:
        return {"verified": False, "reason": "No source result"}
    item = result[0] if isinstance(result[0], dict) else {}
    source_code = str(item.get("SourceCode") or "")
    return {
        "verified": bool(source_code.strip()),
        "contract_name": item.get("ContractName"),
        "compiler_version": item.get("CompilerVersion"),
        "source_code": source_code,
        "abi": item.get("ABI"),
        "raw": item,
    }
