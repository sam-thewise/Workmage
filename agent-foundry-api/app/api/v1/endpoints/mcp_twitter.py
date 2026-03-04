"""Twitter/X MCP endpoint proxied to twitter-automation service."""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Request, Response
import httpx

from app.core.config import settings

router = APIRouter(prefix="/mcp/twitter", tags=["mcp-twitter"])
logger = logging.getLogger(__name__)

DEFAULT_TOOLS_LIST: list[dict[str, Any]] = [
    {
        "name": "fetch_x_profile_timeline",
        "description": "Fetch recent posts from an X profile by handle. Default limit=10; use up to 20 for personality. Higher limits use more API quota.",
        "inputSchema": {"type": "object", "properties": {"handle": {"type": "string"}, "limit": {"type": "integer", "description": "Posts to fetch (default 10, max 20)."}}, "required": ["handle"]},
    },
    {
        "name": "fetch_x_post",
        "description": "Fetch a single X post by URL or post id.",
        "inputSchema": {"type": "object", "properties": {"url_or_id": {"type": "string"}}, "required": ["url_or_id"]},
    },
    {
        "name": "search_x_posts",
        "description": "Search latest X posts by query. Default limit=10, max 20 to conserve API quota.",
        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "description": "Posts to return (default 10, max 20)."}}, "required": ["query"]},
    },
    {
        "name": "check_x_sessions",
        "description": "Check Twitter API connectivity and status.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _ok_text(payload: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload)}]}


def _error_text(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": f"Twitter source error: {message}"}]}


def _proxy_jsonrpc(method: str, params: dict[str, Any], req_id: Any) -> dict[str, Any]:
    body = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
    last_error: Exception | None = None
    for attempt in range(1, max(1, settings.TWITTER_MCP_RETRIES) + 1):
        try:
            logger.info("twitter_mcp_proxy method=%s attempt=%s", method, attempt)
            with httpx.Client(timeout=settings.TWITTER_MCP_TIMEOUT_SEC) as client:
                resp = client.post(settings.TWITTER_MCP_URL, json=body)
            resp.raise_for_status()
            payload = resp.json()
            if isinstance(payload, dict) and isinstance(payload.get("result"), dict):
                return payload["result"]
            if isinstance(payload, dict) and payload.get("error"):
                return _error_text(f"Upstream error: {payload['error']}")
            return _error_text("Invalid upstream response shape.")
        except Exception as exc:
            last_error = exc
            logger.warning("twitter_mcp_proxy_failure method=%s attempt=%s err=%s", method, attempt, type(exc).__name__)
            if attempt >= max(1, settings.TWITTER_MCP_RETRIES):
                break
    return _error_text(f"Upstream MCP proxy failure: {last_error}")


def _handle_tools_list(req_id: Any) -> dict[str, Any]:
    result = _proxy_jsonrpc("tools/list", {}, req_id)
    if result.get("content"):
        return {"tools": DEFAULT_TOOLS_LIST}
    tools = result.get("tools")
    if isinstance(tools, list) and tools:
        return {"tools": tools}
    return {"tools": DEFAULT_TOOLS_LIST}


def _handle_tools_call(params: dict[str, Any], req_id: Any) -> dict[str, Any]:
    result = _proxy_jsonrpc("tools/call", params, req_id)
    if result.get("content"):
        return result
    return _ok_text({"error": "Upstream tools/call returned no content."})


@router.post("")
async def mcp_twitter_jsonrpc(request: Request) -> Response:
    """Handle MCP JSON-RPC methods: tools/list and tools/call."""
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
        result = _handle_tools_list(req_id)
    elif method == "tools/call":
        result = _handle_tools_call(params, req_id)
    else:
        return Response(
            content=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }
            ),
            status_code=200,
            media_type="application/json",
        )
    return Response(
        content=json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}),
        status_code=200,
        media_type="application/json",
    )

