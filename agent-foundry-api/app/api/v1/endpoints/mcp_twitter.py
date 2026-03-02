"""Twitter/X MCP endpoint backed by internal TwitterSourceService."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request, Response

from app.services.twitter_source import (
    TwitterConfigurationError,
    TwitterSourceError,
    TwitterUpstreamError,
    get_twitter_source_service,
)

router = APIRouter(prefix="/mcp/twitter", tags=["mcp-twitter"])

TOOLS_LIST: list[dict[str, Any]] = [
    {
        "name": "fetch_x_profile_timeline",
        "description": "Fetch recent posts from an X profile by handle.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "handle": {"type": "string", "description": "X handle (with or without @)."},
                "limit": {"type": "integer", "description": "Maximum posts to return (1-50). Default 10."},
            },
            "required": ["handle"],
        },
    },
    {
        "name": "fetch_x_post",
        "description": "Fetch a single X post by URL or post id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url_or_id": {"type": "string", "description": "Full x.com status URL or numeric post id."},
            },
            "required": ["url_or_id"],
        },
    },
    {
        "name": "search_x_posts",
        "description": "Search latest X posts by query.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query."},
                "limit": {"type": "integer", "description": "Maximum posts to return (1-50). Default 10."},
            },
            "required": ["query"],
        },
    },
]


def _ok_text(payload: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload)}]}


def _error_text(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": f"Twitter source error: {message}"}]}


def _handle_tools_list() -> dict[str, Any]:
    return {"tools": TOOLS_LIST}


def _handle_tools_call(params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name") or ""
    args = params.get("arguments") or {}
    service = get_twitter_source_service()
    try:
        if name == "fetch_x_profile_timeline":
            handle = args.get("handle") or ""
            limit = args.get("limit") or 10
            return _ok_text(service.fetch_profile_timeline(handle=handle, limit=limit))
        if name == "fetch_x_post":
            url_or_id = args.get("url_or_id") or ""
            return _ok_text(service.fetch_post(url_or_id=url_or_id))
        if name == "search_x_posts":
            query = args.get("query") or ""
            limit = args.get("limit") or 10
            return _ok_text(service.search_posts(query=query, limit=limit))
        return _error_text(f"Unknown tool: {name}")
    except (ValueError, TwitterConfigurationError) as exc:
        return _error_text(str(exc))
    except TwitterUpstreamError as exc:
        status = f" (status {exc.status_code})" if exc.status_code else ""
        return _error_text(f"{exc}{status}")
    except TwitterSourceError as exc:
        return _error_text(str(exc))
    except Exception as exc:
        return _error_text(f"Unexpected error: {exc}")


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
        result = _handle_tools_list()
    elif method == "tools/call":
        result = _handle_tools_call(params)
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

