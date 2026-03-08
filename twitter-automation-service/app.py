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
        "description": "Fetch posts from an X profile by handle. Optional start_time and end_time (ISO 8601, e.g. 2024-01-01T00:00:00Z) filter posts by date. Without dates, returns most recent posts. Default limit=10; use up to 100 with date range for full coverage.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "handle": {"type": "string", "description": "X handle with or without @."},
                "limit": {"type": "integer", "description": "Number of posts (default 10, max 20 without dates, max 100 with start_time/end_time)."},
                "start_time": {"type": "string", "description": "ISO 8601 start of date range (e.g. 2024-01-01T00:00:00Z or 2024-01-01). Inclusive."},
                "end_time": {"type": "string", "description": "ISO 8601 end of date range (e.g. 2024-03-31T23:59:59Z or 2024-03-31). Inclusive."},
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
    created_at = tweet.get("created_at") or ""
    return {
        "id": tid,
        "author_handle": author_handle,
        "text": text,
        "url": url,
        "created_at": created_at,
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


def _normalize_iso8601(value: str | None, is_end: bool = False) -> str | None:
    """Convert YYYY-MM-DD to ISO 8601; pass through if already ISO 8601."""
    v = (value or "").strip()
    if not v:
        return None
    # Already has T (full ISO 8601)
    if "T" in v:
        return v if v.endswith("Z") else f"{v}Z"
    # YYYY-MM-DD -> append time
    if len(v) == 10 and v[4] == "-" and v[7] == "-":
        return f"{v}T23:59:59Z" if is_end else f"{v}T00:00:00Z"
    return v


def _fetch_profile_timeline(
    handle: str,
    limit: int | None = 10,
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict[str, Any]:
    normalized = (handle or "").strip().lstrip("@")
    if not normalized:
        raise ValueError("handle is required")

    has_date_range = bool((start_time or "").strip()) or bool((end_time or "").strip())
    max_limit = 100 if has_date_range else MAX_TIMELINE_LIMIT
    limit = max(1, min(max_limit, int(limit or DEFAULT_TIMELINE_LIMIT)))

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

        # User timeline: API supports start_time, end_time (ISO 8601)
        req_params: dict[str, Any] = {
            "max_results": max(5, min(100, limit)),
            "exclude": "replies,retweets",
            "tweet.fields": "created_at,text,author_id",
            "expansions": "author_id",
            "user.fields": "username",
        }
        st = _normalize_iso8601(start_time, is_end=False)
        et = _normalize_iso8601(end_time, is_end=True)
        if st:
            req_params["start_time"] = st
        if et:
            req_params["end_time"] = et

        r2 = client.get(
            f"{API_BASE}/users/{user_id}/tweets",
            headers=_auth_headers(),
            params=req_params,
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
            return _fetch_profile_timeline(
                args.get("handle") or "",
                args.get("limit") or DEFAULT_TIMELINE_LIMIT,
                args.get("start_time") or None,
                args.get("end_time") or None,
            )
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
