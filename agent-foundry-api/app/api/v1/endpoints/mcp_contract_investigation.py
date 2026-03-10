"""Contract investigation MCP: transactions by date range, caller analysis, contract source.

Fuji-first; network parameter supports avalanche later.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Request, Response

from app.services.contract_investigation import (
    get_contract_callers_analysis,
    get_contract_period_metrics,
    get_contract_transactions,
)
from app.services.contract_source import fetch_verified_source

logger = logging.getLogger(__name__)

TOOLS_LIST: list[dict[str, Any]] = [
    {
        "name": "get_contract_transactions",
        "description": "List all transactions for a contract within a date range. Use for reports or content generation. Returns hash, from, to, value, timeStamp, etc. Dates are UTC unless timezone is set; range is clamped to the indexer's latest block so 'today' works.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "contract_address": {"type": "string", "description": "Contract address (0x...)."},
                "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD or ISO datetime)."},
                "end_date": {"type": "string", "description": "End date (YYYY-MM-DD or ISO datetime)."},
                "network": {"type": "string", "description": "Network: fuji or avalanche. Default fuji.", "default": "fuji"},
                "timezone": {"type": "string", "description": "IANA timezone for date-only inputs (e.g. America/New_York). Converts to UTC; omit for UTC."},
            },
            "required": ["contract_address", "start_date", "end_date"],
        },
    },
    {
        "name": "get_contract_source",
        "description": "Get verified contract source code and ABI for a contract.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "contract_address": {"type": "string", "description": "Contract address (0x...)."},
                "network": {"type": "string", "description": "Network: fuji or avalanche. Default fuji.", "default": "fuji"},
            },
            "required": ["contract_address"],
        },
    },
    {
        "name": "get_contract_callers_analysis",
        "description": "Per-caller stats for wallets that interacted with the contract in the period: is_new (first tx on chain in period), first_tx_timestamp, tx_count_on_chain, tx_count_to_contract_in_period. Capped by max_callers to limit API calls. Dates are UTC unless timezone is set; range clamped to indexer latest.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "contract_address": {"type": "string", "description": "Contract address (0x...)."},
                "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD or ISO datetime)."},
                "end_date": {"type": "string", "description": "End date (YYYY-MM-DD or ISO datetime)."},
                "network": {"type": "string", "description": "Network: fuji or avalanche. Default fuji.", "default": "fuji"},
                "max_callers": {"type": "integer", "description": "Max number of callers to analyze (default 100).", "default": 100},
                "timezone": {"type": "string", "description": "IANA timezone for date-only inputs (e.g. America/New_York). Omit for UTC."},
            },
            "required": ["contract_address", "start_date", "end_date"],
        },
    },
    {
        "name": "get_contract_period_metrics",
        "description": "Aggregates for one period: total_tx, unique_callers_count, new_callers_count. Optionally include list of new caller addresses. Use to answer e.g. 'how many new wallets on this date?' or compare two periods for 'visitors week X vs week Y'. Dates are UTC unless timezone is set; range clamped to indexer latest.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "contract_address": {"type": "string", "description": "Contract address (0x...)."},
                "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD or ISO datetime)."},
                "end_date": {"type": "string", "description": "End date (YYYY-MM-DD or ISO datetime)."},
                "network": {"type": "string", "description": "Network: fuji or avalanche. Default fuji.", "default": "fuji"},
                "include_new_callers_list": {"type": "boolean", "description": "Include new_callers_addresses in result.", "default": False},
                "timezone": {"type": "string", "description": "IANA timezone for date-only inputs (e.g. America/New_York). Omit for UTC."},
            },
            "required": ["contract_address", "start_date", "end_date"],
        },
    },
]

router = APIRouter(prefix="/mcp/contract-investigation", tags=["mcp-contract-investigation"])


def _normalize_network(network: Any) -> str:
    if not network or not isinstance(network, str):
        return "fuji"
    n = network.strip().lower()
    return n if n in ("fuji", "avalanche") else "fuji"


def _handle_tools_list() -> dict[str, Any]:
    return {"tools": TOOLS_LIST}


async def _handle_tools_call(params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name") or ""
    args = params.get("arguments") or {}
    try:
        if name == "get_contract_transactions":
            contract_address = (args.get("contract_address") or "").strip()
            start_date = (args.get("start_date") or "").strip()
            end_date = (args.get("end_date") or "").strip()
            network = _normalize_network(args.get("network"))
            timezone_name = (args.get("timezone") or "").strip() or None
            if not contract_address:
                return {"content": [{"type": "text", "text": "contract_address is required"}]}
            if not start_date or not end_date:
                return {"content": [{"type": "text", "text": "start_date and end_date are required"}]}
            txs = await get_contract_transactions(
                contract_address, start_date, end_date, network, timezone_name=timezone_name
            )
            return {"content": [{"type": "text", "text": json.dumps(txs, indent=2)}]}

        if name == "get_contract_source":
            contract_address = (args.get("contract_address") or "").strip()
            network = _normalize_network(args.get("network"))
            if not contract_address:
                return {"content": [{"type": "text", "text": "contract_address is required"}]}
            data = await fetch_verified_source(contract_address, network=network)
            return {"content": [{"type": "text", "text": json.dumps(data, indent=2)}]}

        if name == "get_contract_callers_analysis":
            contract_address = (args.get("contract_address") or "").strip()
            start_date = (args.get("start_date") or "").strip()
            end_date = (args.get("end_date") or "").strip()
            network = _normalize_network(args.get("network"))
            max_callers = max(1, min(500, int(args.get("max_callers") or 100)))
            timezone_name = (args.get("timezone") or "").strip() or None
            if not contract_address:
                return {"content": [{"type": "text", "text": "contract_address is required"}]}
            if not start_date or not end_date:
                return {"content": [{"type": "text", "text": "start_date and end_date are required"}]}
            analyses = await get_contract_callers_analysis(
                contract_address,
                start_date,
                end_date,
                network,
                max_callers=max_callers,
                timezone_name=timezone_name,
            )
            return {"content": [{"type": "text", "text": json.dumps(analyses, indent=2)}]}

        if name == "get_contract_period_metrics":
            contract_address = (args.get("contract_address") or "").strip()
            start_date = (args.get("start_date") or "").strip()
            end_date = (args.get("end_date") or "").strip()
            network = _normalize_network(args.get("network"))
            include_new_callers_list = bool(args.get("include_new_callers_list"))
            timezone_name = (args.get("timezone") or "").strip() or None
            if not contract_address:
                return {"content": [{"type": "text", "text": "contract_address is required"}]}
            if not start_date or not end_date:
                return {"content": [{"type": "text", "text": "start_date and end_date are required"}]}
            metrics = await get_contract_period_metrics(
                contract_address,
                start_date,
                end_date,
                network,
                include_new_callers_list=include_new_callers_list,
                timezone_name=timezone_name,
            )
            return {"content": [{"type": "text", "text": json.dumps(metrics, indent=2)}]}

        return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}]}
    except ValueError as e:
        return {"content": [{"type": "text", "text": str(e)}]}
    except Exception as e:
        logger.exception("contract_investigation MCP tools/call error")
        return {"content": [{"type": "text", "text": f"Error: {e}"}]}


@router.post("")
async def mcp_contract_investigation_jsonrpc(request: Request) -> Response:
    """Handle MCP JSON-RPC: tools/list and tools/call. No auth required (read-only chain data)."""
    try:
        body = await request.json()
    except Exception:
        return Response(
            content=json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}),
            status_code=200,
            media_type="application/json",
        )
    method = body.get("method") if isinstance(body, dict) else None
    req_id = body.get("id") if isinstance(body, dict) else None
    params = body.get("params") if isinstance(body, dict) else {}

    if method == "tools/list":
        result = _handle_tools_list()
    elif method == "tools/call":
        result = await _handle_tools_call(params)
    else:
        return Response(
            content=json.dumps({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }),
            status_code=200,
            media_type="application/json",
        )

    return Response(
        content=json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}),
        status_code=200,
        media_type="application/json",
    )
