"""MCP client helper for manifest-declared servers.

This module provides:
1) server configuration extraction from manifests,
2) MCP tool discovery in OpenAI function format, and
3) resilient MCP tool invocation (retry + timeout).
"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

DEFAULT_TIMEOUT_SEC = 12
DEFAULT_RETRIES = 2
DEFAULT_BACKOFF_SEC = 0.5

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """Validated MCP server config from manifest module."""

    key: str
    name: str
    transport: str
    url: str
    timeout_sec: int = DEFAULT_TIMEOUT_SEC
    retries: int = DEFAULT_RETRIES
    headers: dict[str, str] | None = None


def extract_mcp_servers(manifest: dict[str, Any]) -> dict[str, MCPServerConfig]:
    """Extract MCP server definitions keyed by manifest module key.

    Supported manifest shape:
    {
      "modules": [
        {
          "type": "mcp",
          "name": "avalanche_docs",
          "transport": "http",
          "url": "https://build.avax.network/api/mcp",
          "timeout_sec": 15,
          "retries": 2,
          "headers": {"Authorization": "..."}
        }
      ]
    }
    """
    servers: dict[str, MCPServerConfig] = {}
    modules = manifest.get("modules") or []
    for idx, mod in enumerate(modules):
        if not isinstance(mod, dict):
            continue
        if mod.get("type") != "mcp":
            continue
        key = str(mod.get("key") or mod.get("name") or f"mcp_{idx}")
        transport = str(mod.get("transport") or "http").lower()
        url = str(mod.get("url") or "").strip()
        if not url:
            continue
        servers[key] = MCPServerConfig(
            key=key,
            name=str(mod.get("name") or key),
            transport=transport,
            url=url,
            timeout_sec=int(mod.get("timeout_sec") or DEFAULT_TIMEOUT_SEC),
            retries=max(0, int(mod.get("retries") or DEFAULT_RETRIES)),
            headers=mod.get("headers") if isinstance(mod.get("headers"), dict) else None,
        )
    return servers


def _jsonrpc_call(
    server: MCPServerConfig,
    method: str,
    params: dict[str, Any],
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Call JSON-RPC endpoint with bounded retries and timeout."""
    payload = {"jsonrpc": "2.0", "id": int(time.time() * 1000), "method": method, "params": params}
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if server.headers:
        headers.update({str(k): str(v) for k, v in server.headers.items()})
    if extra_headers:
        headers.update({str(k): str(v) for k, v in extra_headers.items()})

    attempt = 0
    while True:
        try:
            req = urllib.request.Request(server.url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=server.timeout_sec) as response:
                raw = response.read().decode("utf-8")
                data = json.loads(raw) if raw else {}
                if data.get("error"):
                    raise RuntimeError(f"MCP error: {data['error']}")
                return data.get("result") or {}
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt >= server.retries:
                raise RuntimeError(f"MCP call failed after retries ({server.name}): {exc}") from exc
            attempt += 1
            time.sleep(DEFAULT_BACKOFF_SEC * attempt)


def _normalize_tool_schema(tool: dict[str, Any], server_key: str, server_name: str) -> dict[str, Any]:
    """Convert MCP tool descriptor to OpenAI function schema."""
    name = str(tool.get("name") or "")
    if not name:
        raise ValueError("MCP tool is missing name")
    input_schema = tool.get("inputSchema") if isinstance(tool.get("inputSchema"), dict) else {}
    return {
        "name": f"mcp__{server_key}__{name}",
        "description": str(tool.get("description") or f"MCP tool `{name}` from `{server_name}`"),
        "parameters": input_schema or {"type": "object", "properties": {}},
    }


def get_mcp_tools_from_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Discover tools from all MCP modules declared in the manifest."""
    tools: list[dict[str, Any]] = []
    servers = extract_mcp_servers(manifest)
    for key, server in servers.items():
        if server.transport != "http":
            # The first release supports HTTP JSON-RPC MCP endpoints.
            continue
        try:
            result = _jsonrpc_call(server, "tools/list", {})
            server_tools = result.get("tools") if isinstance(result, dict) else []
            if isinstance(server_tools, list):
                for tool in server_tools:
                    if isinstance(tool, dict):
                        tools.append(_normalize_tool_schema(tool, key, server.name))
        except Exception:
            # Discovery failures are non-fatal for the run. Tool call will fail loudly if invoked.
            logger.warning("MCP tools/list failed for server=%s url=%s", server.name, server.url, exc_info=True)
            continue
    return tools


def parse_mcp_tool_name(tool_name: str) -> tuple[str, str] | None:
    """Parse namespaced tool name `mcp__{server_key}__{tool}`."""
    if not tool_name.startswith("mcp__"):
        return None
    parts = tool_name.split("__", 2)
    if len(parts) != 3:
        return None
    return parts[1], parts[2]


def execute_mcp_tool(
    manifest: dict[str, Any],
    tool_name: str,
    arguments: dict[str, Any],
    github_token: str | None = None,
) -> str:
    """Execute a namespaced MCP tool and return normalized text output."""
    parsed = parse_mcp_tool_name(tool_name)
    if not parsed:
        return "Invalid MCP tool name format"
    server_key, inner_tool_name = parsed
    servers = extract_mcp_servers(manifest)
    server = servers.get(server_key)
    if not server:
        return f"MCP server `{server_key}` not found in manifest"
    if server.transport != "http":
        return f"MCP transport `{server.transport}` not supported yet"

    extra_headers = None
    if server_key.lower() == "github" and github_token:
        extra_headers = {"Authorization": f"token {github_token}"}

    try:
        result = _jsonrpc_call(
            server,
            "tools/call",
            {"name": inner_tool_name, "arguments": arguments or {}},
            extra_headers=extra_headers,
        )
    except Exception as exc:
        logger.warning(
            "MCP tools/call failed for server=%s tool=%s url=%s",
            server.name,
            inner_tool_name,
            server.url,
            exc_info=True,
        )
        return f"MCP execution failed: {exc}"

    content = result.get("content") if isinstance(result, dict) else None
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(str(item.get("text") or ""))
            elif isinstance(item, dict):
                text_parts.append(json.dumps(item))
        return "\n".join([p for p in text_parts if p]).strip() or json.dumps(result)
    return json.dumps(result)
