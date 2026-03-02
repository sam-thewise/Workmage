"""MCP (Model Context Protocol) HTTP endpoint for agent tools.

Exposes a single tool: scrape_as_markdown. Fetches a URL, extracts main content
with trafilatura, returns markdown for token-efficient agent use.
"""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Request, Response
import httpx

from trafilatura import extract, fetch_url
from trafilatura.settings import DEFAULT_CONFIG

router = APIRouter(prefix="/mcp", tags=["mcp"])

TOOL_NAME = "scrape_as_markdown"
TOOL_DESCRIPTION = (
    "Fetch a URL and return its main content as markdown. "
    "Uses main-content extraction to reduce tokens (strips nav, ads, footers)."
)
TOOL_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "url": {
            "type": "string",
            "description": "URL to fetch (http or https only).",
        },
        "max_length": {
            "type": "integer",
            "description": "Optional maximum characters to return. Omit for full content.",
        },
        "include_metadata": {
            "type": "boolean",
            "description": "Include title, author, date in the output. Default false.",
            "default": False,
        },
    },
    "required": ["url"],
}

# Safe defaults: 15s timeout, 2MB max download
FETCH_TIMEOUT = 15
MAX_FILE_SIZE = 2 * 1024 * 1024
DEFAULT_MAX_LENGTH = 100_000
HTTP_FALLBACK_TIMEOUT = 20
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}


def _trafilatura_config():
    """Return trafilatura config with timeout and max size limits."""
    config = deepcopy(DEFAULT_CONFIG)
    config["DEFAULT"]["DOWNLOAD_TIMEOUT"] = str(FETCH_TIMEOUT)
    config["DEFAULT"]["MAX_FILE_SIZE"] = str(MAX_FILE_SIZE)
    return config


def _validate_url(url: str) -> None:
    if not url or not isinstance(url, str):
        raise ValueError("url is required and must be a string")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("url must use http or https")
    if not parsed.netloc:
        raise ValueError("url must have a host")


def _scrape_as_markdown(url: str, max_length: int | None = None, include_metadata: bool = False) -> str:
    """Fetch URL and return main content as markdown."""
    config = _trafilatura_config()
    downloaded = fetch_url(url, config=config)
    status_hint = None
    if not downloaded:
        # Fallback for sites where trafilatura downloader returns empty body.
        try:
            with httpx.Client(
                timeout=HTTP_FALLBACK_TIMEOUT,
                follow_redirects=True,
                headers=HTTP_HEADERS,
            ) as client:
                resp = client.get(url)
            status_hint = resp.status_code
            body = resp.text or ""
            if not body.strip():
                raise ValueError(
                    f"Failed to fetch URL: upstream returned status {resp.status_code} with empty body"
                )
            downloaded = body
        except httpx.HTTPError as e:
            raise ValueError(f"Failed to fetch URL via HTTP fallback: {e}") from e
    result = extract(
        downloaded,
        output_format="markdown",
        with_metadata=include_metadata,
        include_links=True,
        include_tables=True,
        config=config,
    )
    if not result:
        if status_hint:
            raise ValueError(
                f"No main content could be extracted (HTTP status {status_hint}; page may block scraping)"
            )
        raise ValueError("No main content could be extracted")
    if max_length is not None and max_length > 0 and len(result) > max_length:
        result = result[:max_length] + "\n\n[... truncated]"
    return result


def _handle_tools_list() -> dict[str, Any]:
    return {
        "tools": [
            {
                "name": TOOL_NAME,
                "description": TOOL_DESCRIPTION,
                "inputSchema": TOOL_INPUT_SCHEMA,
            }
        ]
    }


def _handle_tools_call(params: dict[str, Any]) -> dict[str, Any]:
    args = params.get("arguments") or {}
    name = params.get("name") or ""
    if name != TOOL_NAME:
        return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}]}
    url = args.get("url")
    max_length = args.get("max_length")
    include_metadata = bool(args.get("include_metadata", False))
    try:
        _validate_url(url)
    except ValueError as e:
        return {"content": [{"type": "text", "text": f"Invalid request: {e}"}]}
    if max_length is not None and (not isinstance(max_length, int) or max_length <= 0):
        max_length = DEFAULT_MAX_LENGTH
    try:
        text = _scrape_as_markdown(url, max_length=max_length, include_metadata=include_metadata)
        return {"content": [{"type": "text", "text": text}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Scrape failed: {e}"}]}


@router.post("")
async def mcp_jsonrpc(request: Request) -> Response:
    """Handle MCP JSON-RPC: tools/list and tools/call."""
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
