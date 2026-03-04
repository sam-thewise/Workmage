"""Contract tests for Twitter MCP endpoint."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


class _StubResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _StubClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, json):
        method = json.get("method")
        if method == "tools/list":
            return _StubResponse(
                {
                    "jsonrpc": "2.0",
                    "id": json.get("id"),
                    "result": {
                        "tools": [
                            {"name": "fetch_x_profile_timeline"},
                            {"name": "fetch_x_post"},
                            {"name": "search_x_posts"},
                            {"name": "check_x_sessions"},
                        ]
                    },
                }
            )
        return _StubResponse(
            {
                "jsonrpc": "2.0",
                "id": json.get("id"),
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": '{"handle":"@workmage","count":5}',
                        }
                    ]
                },
            }
        )


@pytest.mark.asyncio
async def test_mcp_twitter_tools_list(monkeypatch):
    from app.api.v1.endpoints import mcp_twitter
    monkeypatch.setattr(mcp_twitter.httpx, "Client", _StubClient)
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
    assert "check_x_sessions" in names


@pytest.mark.asyncio
async def test_mcp_twitter_tools_call(monkeypatch):
    from app.api.v1.endpoints import mcp_twitter

    monkeypatch.setattr(mcp_twitter.httpx, "Client", _StubClient)
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
    assert '"handle":"@workmage"' in text
    assert '"count":5' in text

