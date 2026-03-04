"""Twitter/X MCP service using the official Twitter API v2."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("twitter_automation_service")
logging.basicConfig(level=os.getenv("TWITTER_AUTOMATION_LOG_LEVEL", "INFO"))

API_BASE = "https://api.twitter.com/2"

# Cap per-request to avoid burning Twitter API quota. Default 10; use up to 20 for personality/voice.
DEFAULT_TIMELINE_LIMIT = 10
MAX_TIMELINE_LIMIT = 20

TOOLS_LIST: list[dict[str, Any]] = [
    {
        "name": "fetch_x_profile_timeline",
        "description": "Fetch recent posts from an X profile by handle. Default limit=10; use up to 20 for more samples (e.g. personality). Higher limits use more API quota.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "handle": {"type": "string"},
                "limit": {"type": "integer", "description": "Number of posts (default 10, max 20). Use 10 for trends, up to 20 for personality/voice."},
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
                "url_or_id": {"type": "string"},
            },
            "required": ["url_or_id"],
        },
    },
    {
        "name": "search_x_posts",
        "description": "Search latest X posts by query. Default limit=10, max 20 to conserve API quota.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "description": "Number of posts (default 10, max 20)."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "check_x_sessions",
        "description": "Check Twitter API connectivity and status.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _get_bearer_token() -> str:
    token = (
        os.getenv("TWITTER_BEARER_TOKEN")
        or os.getenv("TWITTER_AUTOMATION_BEARER_TOKEN")
        or ""
    ).strip()
    if not token:
        raise ValueError(
            "TWITTER_BEARER_TOKEN or TWITTER_AUTOMATION_BEARER_TOKEN must be set for Twitter API v2."
        )
    return token


def _auth_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_get_bearer_token()}",
        "Content-Type": "application/json",
    }


def _extract_status_id(url_or_id: str) -> str:
    value = (url_or_id or "").strip()
    if value.isdigit():
        return value
    match = re.search(r"/status/(\d+)", value)
    if match:
        return match.group(1)
    raise ValueError("Could not parse status id from input.")


def _username_from_includes(includes: dict[str, Any] | None, author_id: str | None) -> str:
    if not includes or not author_id:
        return ""
    for u in includes.get("users") or []:
        if u.get("id") == author_id:
            handle = (u.get("username") or "").strip()
            return f"@{handle}" if handle else ""
    return ""


def _tweet_to_payload(tweet: dict[str, Any], includes: dict[str, Any] | None = None) -> dict[str, Any]:
    tid = tweet.get("id") or ""
    author_id = tweet.get("author_id")
    author_handle = _username_from_includes(includes, author_id)
    text = (tweet.get("text") or "").strip()
    username = author_handle.lstrip("@") if author_handle else ""
    url = f"https://x.com/{username}/status/{tid}" if tid and username else ""
    return {
        "id": tid,
        "author_handle": author_handle,
        "text": text,
        "url": url,
    }


def _check_sessions() -> dict[str, Any]:
    """Verify API token by calling a lightweight public endpoint."""
    try:
        _get_bearer_token()
        with httpx.Client(timeout=10.0) as client:
            r = client.get(
                f"{API_BASE}/users/by/username/twitter",
                headers=_auth_headers(),
            )
        if r.status_code == 200:
            return {"status": "ok", "api": "twitter_v2", "authenticated": True}
        return {
            "status": "error",
            "api": "twitter_v2",
            "authenticated": False,
            "message": r.text or f"HTTP {r.status_code}",
        }
    except ValueError as e:
        return {
            "status": "error",
            "api": "twitter_v2",
            "authenticated": False,
            "message": str(e),
        }
    except Exception as e:
        return {
            "status": "error",
            "api": "twitter_v2",
            "authenticated": False,
            "message": str(e),
        }


def _fetch_profile_timeline(handle: str, limit: int = 10) -> dict[str, Any]:
    normalized = (handle or "").strip().lstrip("@")
    if not normalized:
        raise ValueError("handle is required")
    limit = max(1, min(MAX_TIMELINE_LIMIT, int(limit or DEFAULT_TIMELINE_LIMIT)))

    with httpx.Client(timeout=30.0) as client:
        # Resolve username -> user id
        r = client.get(
            f"{API_BASE}/users/by/username/{normalized}",
            headers=_auth_headers(),
        )
        if r.status_code != 200:
            err = r.json() if r.content else {}
            msg = err.get("detail", err.get("errors", r.text))
            raise RuntimeError(f"Twitter API user lookup failed: {msg}")
        data = r.json()
        user_id = (data.get("data") or {}).get("id")
        if not user_id:
            raise RuntimeError(f"User not found: @{normalized}")

        # User timeline: API requires max_results between 5 and 100; we cap at MAX_TIMELINE_LIMIT
        max_results = max(5, min(100, limit))
        r2 = client.get(
            f"{API_BASE}/users/{user_id}/tweets",
            headers=_auth_headers(),
            params={
                "max_results": max_results,
                "exclude": "replies,retweets",
                "tweet.fields": "created_at,text,author_id",
                "expansions": "author_id",
                "user.fields": "username",
            },
        )
        if r2.status_code != 200:
            err = r2.json() if r2.content else {}
            detail = err.get("detail")
            errors = err.get("errors")
            msg = detail if isinstance(detail, str) else (errors if errors else r2.text)
            if isinstance(msg, list):
                msg = "; ".join(str(e) for e in msg)
            elif not isinstance(msg, str):
                msg = json.dumps(msg)
            raise RuntimeError(f"Twitter API timeline failed: {msg}")

        body = r2.json()
        if body.get("errors") and not body.get("data"):
            err_msg = "; ".join(
                e.get("detail", e.get("message", str(e))) for e in body["errors"]
            )
            raise RuntimeError(f"Twitter API timeline failed: {err_msg}")
        tweets = (body.get("data") or [])[:limit]
        includes = body.get("includes") or {}
        posts = [_tweet_to_payload(t, includes) for t in tweets]

    return {
        "source": "twitter_api",
        "handle": f"@{normalized}",
        "count": len(posts),
        "posts": posts,
    }


def _fetch_post(url_or_id: str) -> dict[str, Any]:
    status_id = _extract_status_id(url_or_id)

    with httpx.Client(timeout=30.0) as client:
        r = client.get(
            f"{API_BASE}/tweets/{status_id}",
            headers=_auth_headers(),
            params={
                "tweet.fields": "created_at,text,author_id",
                "expansions": "author_id",
                "user.fields": "username",
            },
        )
        if r.status_code != 200:
            err = r.json() if r.content else {}
            msg = err.get("detail", err.get("errors", r.text))
            raise RuntimeError(f"Twitter API tweet lookup failed: {msg}")

        body = r.json()
        data = body.get("data")
        if not data:
            raise RuntimeError("Tweet not found or not available.")
        includes = body.get("includes") or {}
        post = _tweet_to_payload(data, includes)

    return {"source": "twitter_api", "post": post}


def _search_posts(query: str, limit: int = 10) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        raise ValueError("query is required")
    limit = max(1, min(MAX_TIMELINE_LIMIT, int(limit or DEFAULT_TIMELINE_LIMIT)))

    with httpx.Client(timeout=30.0) as client:
        r = client.get(
            f"{API_BASE}/tweets/search/recent",
            headers=_auth_headers(),
            params={
                "query": q,
                "max_results": min(100, limit),  # API max 100; we cap at MAX_TIMELINE_LIMIT
                "tweet.fields": "created_at,text,author_id",
                "expansions": "author_id",
                "user.fields": "username",
            },
        )
        if r.status_code != 200:
            err = r.json() if r.content else {}
            msg = err.get("detail", err.get("errors", r.text))
            raise RuntimeError(f"Twitter API search failed: {msg}")

        body = r.json()
        tweets = (body.get("data") or [])[:limit]
        includes = body.get("includes") or {}
        posts = [_tweet_to_payload(t, includes) for t in tweets]

    return {
        "source": "twitter_api",
        "query": q,
        "count": len(posts),
        "posts": posts,
    }


app = FastAPI(title="Twitter Automation MCP Service")


def _content_text(payload: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload)}]}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/mcp/twitter")
async def mcp_twitter(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}},
            status_code=200,
        )
    method = body.get("method")
    req_id = body.get("id")
    params = body.get("params") or {}

    if method == "tools/list":
        return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS_LIST}}, status_code=200)
    if method != "tools/call":
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            },
            status_code=200,
        )

    name = params.get("name") or ""
    args = params.get("arguments") or {}
    operation_timeout = int(os.getenv("TWITTER_AUTOMATION_OPERATION_TIMEOUT_SEC", "45"))

    def _run_tool() -> dict[str, Any]:
        if name == "fetch_x_profile_timeline":
            return _fetch_profile_timeline(args.get("handle") or "", args.get("limit") or DEFAULT_TIMELINE_LIMIT)
        if name == "fetch_x_post":
            return _fetch_post(args.get("url_or_id") or "")
        if name == "search_x_posts":
            return _search_posts(args.get("query") or "", args.get("limit") or DEFAULT_TIMELINE_LIMIT)
        if name == "check_x_sessions":
            return _check_sessions()
        return {"error": f"Unknown tool: {name}"}

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_run_tool),
            timeout=operation_timeout,
        )
    except asyncio.TimeoutError:
        result = {
            "error": f"Twitter automation service timed out after {operation_timeout}s."
        }
    except Exception as exc:
        result = {"error": f"Twitter automation service failed: {exc}"}

    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": _content_text(result)}, status_code=200)
