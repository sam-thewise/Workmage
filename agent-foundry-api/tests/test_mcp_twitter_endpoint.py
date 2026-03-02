"""Contract tests for Twitter MCP endpoint."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


class _StubTwitterService:
    def fetch_profile_timeline(self, handle: str, limit: int = 10):
        return {"handle": handle, "count": int(limit), "posts": []}

    def fetch_post(self, url_or_id: str):
        return {"post": {"id": str(url_or_id), "text": "hello"}}

    def search_posts(self, query: str, limit: int = 10):
        return {"query": query, "count": int(limit), "posts": []}


@pytest.mark.asyncio
async def test_mcp_twitter_tools_list():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/mcp/twitter",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
    assert res.status_code == 200
    payload = res.json()
    tools = payload["result"]["tools"]
    names = [t["name"] for t in tools]
    assert "fetch_x_profile_timeline" in names
    assert "fetch_x_post" in names
    assert "search_x_posts" in names


@pytest.mark.asyncio
async def test_mcp_twitter_tools_call(monkeypatch):
    from app.api.v1.endpoints import mcp_twitter

    monkeypatch.setattr(mcp_twitter, "get_twitter_source_service", lambda: _StubTwitterService())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/mcp/twitter",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "fetch_x_profile_timeline",
                    "arguments": {"handle": "@workmage", "limit": 5},
                },
            },
        )
    assert res.status_code == 200
    payload = res.json()
    text = payload["result"]["content"][0]["text"]
    assert '"handle": "@workmage"' in text
    assert '"count": 5' in text

