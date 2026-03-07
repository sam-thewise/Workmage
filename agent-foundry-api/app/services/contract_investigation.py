"""Contract investigation service: tx list by date range, caller analysis, period metrics.

Uses Snowtrace/Routescan Etherscan-compatible API (Fuji and mainnet).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import settings
from app.services.contract_source import _snowtrace_base_url

# Max tx per Etherscan txlist request
TXLIST_PAGE_SIZE = 10000

# Default cap on callers to analyze (each triggers one API call)
DEFAULT_MAX_CALLERS = 100


def _parse_date(s: str) -> int:
    """Parse YYYY-MM-DD or ISO datetime to Unix timestamp (UTC)."""
    s = (s or "").strip()
    if not s:
        raise ValueError("Date is required")
    # Try date only first
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(s.replace("Z", "+00:00"), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except ValueError:
            continue
    raise ValueError(f"Invalid date format: {s}. Use YYYY-MM-DD or ISO datetime.")


def _date_range_to_timestamps(start_date: str, end_date: str) -> tuple[int, int]:
    """Return (start_ts, end_ts) for the given date range. end_ts is end of end_date day."""
    start_ts = _parse_date(start_date)
    end_ts = _parse_date(end_date)
    # If only date given (YYYY-MM-DD), end_ts is start of that day; set to end of day
    if re.match(r"^\d{4}-\d{2}-\d{2}$", (end_date or "").strip()):
        end_dt = datetime.fromtimestamp(end_ts, tz=timezone.utc)
        end_ts = int(end_dt.replace(hour=23, minute=59, second=59, microsecond=999999).timestamp())
    if start_ts > end_ts:
        raise ValueError("start_date must be before or equal to end_date")
    return start_ts, end_ts


def _validate_contract_address(contract_address: str) -> None:
    if not contract_address or not isinstance(contract_address, str):
        raise ValueError("contract_address is required")
    addr = contract_address.strip()
    if not re.match(r"^0x[a-fA-F0-9]{40}$", addr):
        raise ValueError("contract_address must be a valid 0x-prefixed 40-char hex address")


async def _snowtrace_request(
    network: str,
    module: str,
    action: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call Snowtrace/Routescan Etherscan-compatible API."""
    base = _snowtrace_base_url(network)
    q = {"module": module, "action": action, **(params or {})}
    if settings.SNOWTRACE_API_KEY:
        q["apikey"] = settings.SNOWTRACE_API_KEY
    async with httpx.AsyncClient(timeout=settings.ACTIONS_HTTP_TIMEOUT_SEC) as client:
        response = await client.get(base, params=q)
        response.raise_for_status()
        data = response.json()
    if data.get("status") == "0" and data.get("message") != "No transactions found":
        msg = data.get("message", "Unknown API error")
        result = data.get("result")
        if isinstance(result, str):
            msg = f"{msg}: {result}"
        raise ValueError(msg)
    return data


async def get_block_number_by_time(
    timestamp: int,
    closest: str,
    network: str = "fuji",
) -> int:
    """Get block number closest to Unix timestamp. closest in ('before', 'after')."""
    data = await _snowtrace_request(
        network,
        "block",
        "getblocknobytime",
        {"timestamp": timestamp, "closest": closest},
    )
    result = data.get("result")
    if result is None:
        raise ValueError("No block number returned")
    return int(result)


async def get_contract_transactions(
    contract_address: str,
    start_date: str,
    end_date: str,
    network: str = "fuji",
) -> list[dict[str, Any]]:
    """List all normal transactions for a contract in a date range. Paginates automatically."""
    _validate_contract_address(contract_address)
    start_ts, end_ts = _date_range_to_timestamps(start_date, end_date)
    start_block = await get_block_number_by_time(start_ts, "after", network)
    end_block = await get_block_number_by_time(end_ts, "before", network)
    if start_block > end_block:
        return []

    out: list[dict[str, Any]] = []
    page = 1
    while True:
        data = await _snowtrace_request(
            network,
            "account",
            "txlist",
            {
                "address": contract_address.strip(),
                "startblock": start_block,
                "endblock": end_block,
                "page": page,
                "offset": TXLIST_PAGE_SIZE,
                "sort": "asc",
            },
        )
        result = data.get("result")
        if not result:
            break
        if isinstance(result, list):
            out.extend(result)
            if len(result) < TXLIST_PAGE_SIZE:
                break
        else:
            break
        page += 1
    return out


async def get_contract_callers_analysis(
    contract_address: str,
    start_date: str,
    end_date: str,
    network: str = "fuji",
    max_callers: int = DEFAULT_MAX_CALLERS,
) -> list[dict[str, Any]]:
    """For each unique caller of the contract in the period, return stats: is_new, first_tx_on_chain, tx_count_on_chain, tx_count_to_contract."""
    _validate_contract_address(contract_address)
    start_ts, end_ts = _date_range_to_timestamps(start_date, end_date)
    txs = await get_contract_transactions(contract_address, start_date, end_date, network)
    # Count tx per from-address in this period
    from_counts: dict[str, int] = {}
    for tx in txs:
        from_addr = (tx.get("from") or "").strip()
        if from_addr and re.match(r"^0x[a-fA-F0-9]{40}$", from_addr):
            from_counts[from_addr] = from_counts.get(from_addr, 0) + 1

    callers = list(from_counts.keys())[:max_callers]
    analyses: list[dict[str, Any]] = []
    for addr in callers:
        # Get first tx on chain for this address (sort=asc, page=1, offset=1)
        try:
            data = await _snowtrace_request(
                network,
                "account",
                "txlist",
                {
                    "address": addr,
                    "startblock": 0,
                    "endblock": 99999999,
                    "page": 1,
                    "offset": 1,
                    "sort": "asc",
                },
            )
        except Exception:
            analyses.append({
                "address": addr,
                "tx_count_to_contract_in_period": from_counts[addr],
                "tx_count_on_chain": None,
                "first_tx_timestamp": None,
                "is_new": None,
                "error": "Failed to fetch account tx list",
            })
            continue
        result = data.get("result")
        first_tx = None
        total_count = 0
        if isinstance(result, list) and result:
            first_tx = result[0]
            total_count = len(result)
        elif isinstance(result, list):
            total_count = 0
        # If we got 1 result, total might be 1 or more; API doesn't give total count. Use len(result) for single page.
        # For "total tx on chain" we'd need to paginate; for performance we report "at least 1" or "1" when we only fetched 1.
        tx_count_on_chain = total_count if isinstance(result, list) else 0
        first_tx_ts = None
        if first_tx and isinstance(first_tx, dict):
            ts = first_tx.get("timeStamp")
            if ts is not None:
                first_tx_ts = int(ts) if isinstance(ts, str) else ts
        is_new = False
        if first_tx_ts is not None:
            is_new = start_ts <= first_tx_ts <= end_ts
        analyses.append({
            "address": addr,
            "tx_count_to_contract_in_period": from_counts[addr],
            "tx_count_on_chain": tx_count_on_chain,
            "first_tx_timestamp": first_tx_ts,
            "is_new": is_new,
        })
    return analyses


async def get_contract_period_metrics(
    contract_address: str,
    start_date: str,
    end_date: str,
    network: str = "fuji",
    include_new_callers_list: bool = False,
    max_callers: int = DEFAULT_MAX_CALLERS,
) -> dict[str, Any]:
    """Aggregates for the period: total_tx, unique_callers_count, new_callers_count, optionally new_callers_addresses."""
    _validate_contract_address(contract_address)
    txs = await get_contract_transactions(contract_address, start_date, end_date, network)
    unique_callers = set()
    for tx in txs:
        from_addr = (tx.get("from") or "").strip()
        if from_addr and re.match(r"^0x[a-fA-F0-9]{40}$", from_addr):
            unique_callers.add(from_addr)
    analyses = await get_contract_callers_analysis(
        contract_address, start_date, end_date, network, max_callers=max_callers
    )
    new_count = sum(1 for a in analyses if a.get("is_new") is True)
    new_addresses = [a["address"] for a in analyses if a.get("is_new") is True] if include_new_callers_list else None
    return {
        "total_tx": len(txs),
        "unique_callers_count": len(unique_callers),
        "new_callers_count": new_count,
        "new_callers_addresses": new_addresses,
        "start_date": start_date,
        "end_date": end_date,
        "network": network,
        "contract_address": contract_address.strip(),
    }
