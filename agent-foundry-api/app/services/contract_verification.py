"""Contract verification on Snowtrace/Routescan (Etherscan-compatible)."""
from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings


def _snowtrace_url(network: str) -> str:
    if network == "fuji":
        return (getattr(settings, "SNOWTRACE_FUJI_API_URL", None) or "").rstrip("/") or "https://api.routescan.io/v2/network/testnet/evm/43113/etherscan/api"
    return settings.SNOWTRACE_API_URL.rstrip("/")


async def submit_verification(
    network: str,
    contract_address: str,
    source_code: str,
    contract_name: str,
    compiler_version: str,
    optimization_used: bool = False,
    runs: int = 200,
    constructor_arguments: str | None = None,
) -> dict[str, Any]:
    """Submit contract source for verification. Returns guid on success for status polling."""
    endpoint = _snowtrace_url(network)
    if not endpoint:
        return {"ok": False, "error": f"No Snowtrace API URL for network {network}"}

    params: dict[str, Any] = {
        "module": "contract",
        "action": "verifysourcecode",
        "address": contract_address,
        "sourceCode": source_code,
        "codeformat": "solidity-single-file",
        "contractname": contract_name,
        "compilerversion": compiler_version,
        "optimizationUsed": "1" if optimization_used else "0",
        "runs": runs,
    }
    if constructor_arguments:
        params["constructorArguements"] = constructor_arguments
    if settings.SNOWTRACE_API_KEY:
        params["apikey"] = settings.SNOWTRACE_API_KEY

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(endpoint, data=params)
        response.raise_for_status()
        data = response.json()

    if data.get("status") == "1" and data.get("message") == "OK":
        guid = data.get("result")
        return {"ok": True, "guid": guid, "message": data.get("message")}
    return {
        "ok": False,
        "error": data.get("message", "Verification failed"),
        "result": data.get("result"),
    }


async def check_verification_status(network: str, guid: str) -> dict[str, Any]:
    """Check verification submission status. Returns success/fail when done."""
    endpoint = _snowtrace_url(network)
    if not endpoint:
        return {"ok": False, "error": f"No Snowtrace API URL for network {network}"}

    params = {
        "module": "contract",
        "action": "checkverifystatus",
        "guid": guid,
    }
    if settings.SNOWTRACE_API_KEY:
        params["apikey"] = settings.SNOWTRACE_API_KEY

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(endpoint, params=params)
        response.raise_for_status()
        data = response.json()

    if data.get("status") == "1":
        return {"ok": True, "verified": True, "message": data.get("message")}
    if "Fail" in str(data.get("result", "")) or "Error" in str(data.get("message", "")):
        return {"ok": True, "verified": False, "message": data.get("message"), "result": data.get("result")}
    return {"ok": True, "pending": True, "message": data.get("message"), "result": data.get("result")}
