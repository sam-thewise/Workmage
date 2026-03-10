"""Tests for contract investigation MCP endpoint (Fuji)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_mcp_contract_investigation_tools_list():
    """tools/list returns all four contract investigation tools."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/mcp/contract-investigation",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
    assert res.status_code == 200
    payload = res.json()
    assert "result" in payload
    tools = payload["result"]["tools"]
    names = [t["name"] for t in tools]
    assert "get_contract_transactions" in names
    assert "get_contract_source" in names
    assert "get_contract_callers_analysis" in names
    assert "get_contract_period_metrics" in names


@pytest.mark.asyncio
async def test_mcp_contract_investigation_tools_call_get_contract_period_metrics():
    """tools/call get_contract_period_metrics returns total_tx, unique_callers_count, new_callers_count."""
    with (
        patch(
            "app.api.v1.endpoints.mcp_contract_investigation.get_contract_transactions",
            new_callable=AsyncMock,
            return_value=[
                {"from": "0x1111111111111111111111111111111111111111", "hash": "0xabc"},
                {"from": "0x1111111111111111111111111111111111111111", "hash": "0xdef"},
                {"from": "0x2222222222222222222222222222222222222222", "hash": "0x123"},
            ],
        ),
        patch(
            "app.api.v1.endpoints.mcp_contract_investigation.get_contract_callers_analysis",
            new_callable=AsyncMock,
            return_value=[
                {
                    "address": "0x1111111111111111111111111111111111111111",
                    "tx_count_to_contract_in_period": 2,
                    "tx_count_on_chain": 1,
                    "first_tx_timestamp": 1709251200,
                    "is_new": True,
                },
                {
                    "address": "0x2222222222222222222222222222222222222222",
                    "tx_count_to_contract_in_period": 1,
                    "tx_count_on_chain": 5,
                    "first_tx_timestamp": 1709000000,
                    "is_new": False,
                },
            ],
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            res = await client.post(
                "/api/v1/mcp/contract-investigation",
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "get_contract_period_metrics",
                        "arguments": {
                            "contract_address": "0x1234567890123456789012345678901234567890",
                            "start_date": "2024-03-01",
                            "end_date": "2024-03-02",
                            "network": "fuji",
                        },
                    },
                },
            )
    assert res.status_code == 200
    payload = res.json()
    text = payload["result"]["content"][0]["text"]
    assert "total_tx" in text
    assert "unique_callers_count" in text
    assert "new_callers_count" in text
    assert "3" in text  # total_tx
    assert "2" in text  # unique callers
    assert "1" in text  # new callers


@pytest.mark.asyncio
async def test_mcp_contract_investigation_tools_call_missing_args():
    """tools/call with missing contract_address returns error text."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/mcp/contract-investigation",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "get_contract_transactions",
                    "arguments": {"start_date": "2024-03-01", "end_date": "2024-03-02"},
                },
            },
        )
    assert res.status_code == 200
    payload = res.json()
    text = payload["result"]["content"][0]["text"]
    assert "contract_address" in text.lower() or "required" in text.lower()


@pytest.mark.asyncio
async def test_contract_investigation_service_date_parsing_and_block_range():
    """Service: date range is converted to block range via getblocknobytime; range clamped to indexer latest."""
    from app.services import contract_investigation

    # Latest block ts after 2024-03-02 so no clamping; then start/end block lookups
    mock_latest_ts = AsyncMock(return_value=2000000000)
    mock_block = AsyncMock(side_effect=[1000, 2000])
    mock_request = AsyncMock(return_value={"result": []})
    with (
        patch.object(
            contract_investigation,
            "get_latest_block_timestamp",
            mock_latest_ts,
        ),
        patch.object(
            contract_investigation,
            "get_block_number_by_time",
            mock_block,
        ),
        patch.object(
            contract_investigation,
            "_snowtrace_request",
            mock_request,
        ),
    ):
        txs = await contract_investigation.get_contract_transactions(
            "0x1234567890123456789012345678901234567890",
            "2024-03-01",
            "2024-03-02",
            "fuji",
        )
        assert txs == []
        assert mock_latest_ts.await_count == 1
        assert mock_block.await_count == 2
        # First call: start_ts -> block (after); second: end_ts -> block (before)
        calls = mock_block.await_args_list
        args0, _ = calls[0][0], calls[0][1]
        args1, _ = calls[1][0], calls[1][1]
        assert args0[1] == "after"
        assert args1[1] == "before"


@pytest.mark.asyncio
async def test_contract_investigation_service_new_caller_logic():
    """Service: is_new is True when first_tx_timestamp falls inside period."""
    from app.services import contract_investigation

    # Period: 2024-03-01 00:00 to 2024-03-02 23:59. first_tx in that range -> is_new
    with (
        patch.object(
            contract_investigation,
            "get_contract_transactions",
            new_callable=AsyncMock,
            return_value=[
                {"from": "0x1111111111111111111111111111111111111111"},
            ],
        ),
        patch.object(
            contract_investigation,
            "_snowtrace_request",
            new_callable=AsyncMock,
            return_value={
                "result": [
                    {
                        "timeStamp": "1709251200",  # 2024-03-01 12:00 UTC
                        "hash": "0xfirst",
                    }
                ]
            },
        ),
    ):
        analyses = await contract_investigation.get_contract_callers_analysis(
            "0x1234567890123456789012345678901234567890",
            "2024-03-01",
            "2024-03-02",
            "fuji",
            max_callers=10,
        )
    assert len(analyses) == 1
    assert analyses[0]["address"] == "0x1111111111111111111111111111111111111111"
    assert analyses[0]["is_new"] is True
    assert analyses[0]["first_tx_timestamp"] == 1709251200
