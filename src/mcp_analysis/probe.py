"""MCP server probe module.

Connects to local (stdio) and remote (HTTP) MCP servers,
calls tools/list, and returns the raw tool definitions.
"""

from __future__ import annotations

import asyncio
import json
import os
import re

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .env import resolve_environment, resolve_headers
from .tokenizer import count_tokens
from .types import McpServerConfig, ServerResult, ToolAnalysis
from . import __version__


async def probe_server(config: McpServerConfig, timeout_s: float) -> ServerResult:
    """Probe a single MCP server and return its tool definitions."""
    result = ServerResult(name=config.name, type=config.type)

    try:
        if config.type == "local":
            tools = await _probe_local(config, timeout_s)
        else:
            tools = await _probe_remote(config, timeout_s)

        result.tools = tools
        result.total_chars = sum(t.char_count for t in tools)

        all_json = "\n".join(t.raw_json for t in tools)
        tc = count_tokens(all_json)
        result.estimated_tokens = tc.estimated
        result.exact_tokens = tc.exact
    except Exception as exc:
        result.error = str(exc)[:200]

    return result


# ─── Local server (stdio) ──────────────────────────────────────────────


async def _probe_local(config: McpServerConfig, timeout_s: float) -> list[ToolAnalysis]:
    if not config.command:
        raise RuntimeError("No command specified for local server")

    env = {**os.environ, **resolve_environment(config.environment)}

    server_params = StdioServerParameters(
        command=config.command[0],
        args=config.command[1:],
        env=env,
    )

    # Redirect server stderr to devnull to prevent log noise from leaking
    # into our terminal (e.g. open-meteo's JSON log lines).
    with open(os.devnull, "w") as devnull:
        async with stdio_client(server_params, errlog=devnull) as (read, write):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(session.initialize(), timeout=timeout_s)
                response = await asyncio.wait_for(session.list_tools(), timeout=timeout_s)
                return [_tool_to_analysis(t) for t in response.tools]


# ─── Remote server (HTTP JSON-RPC) ────────────────────────────────────


async def _probe_remote(config: McpServerConfig, timeout_s: float) -> list[ToolAnalysis]:
    if not config.url:
        raise RuntimeError("No URL specified for remote server")

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        **resolve_headers(config.headers),
    }

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        # Step 1: Initialize
        init_resp = await client.post(
            config.url,
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "mcp-analysis", "version": __version__},
                },
                "id": 1,
            },
        )

        session_id = init_resp.headers.get("mcp-session")

        # Step 2: List tools
        tool_headers = {**headers}
        if session_id:
            tool_headers["Mcp-Session"] = session_id

        tool_resp = await client.post(
            config.url,
            headers=tool_headers,
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 2},
        )

        data = _parse_jsonrpc_response(tool_resp.text)
        tools: list[dict] = data.get("result", {}).get("tools", [])
        return [_tool_to_analysis(t) for t in tools]


# ─── Helpers ───────────────────────────────────────────────────────────


def _tool_to_analysis(tool: object) -> ToolAnalysis:
    """Convert an MCP tool (dict or pydantic model) to ToolAnalysis."""
    if hasattr(tool, "model_dump"):
        d = tool.model_dump()  # type: ignore[union-attr]
    elif isinstance(tool, dict):
        d = tool
    else:
        d = {"name": str(tool)}

    raw = json.dumps(d)
    return ToolAnalysis(
        name=d.get("name", "unknown"),
        description=d.get("description", ""),
        char_count=len(raw),
        raw_json=raw,
    )


def _parse_jsonrpc_response(text: str) -> dict:
    """Parse a JSON-RPC response that may be plain JSON or SSE-wrapped."""
    trimmed = text.strip()
    if trimmed.startswith("{") or trimmed.startswith("["):
        return json.loads(trimmed)

    # SSE format: extract last "data:" line containing JSON
    for line in reversed(trimmed.split("\n")):
        line = line.strip()
        if line.startswith("data:"):
            json_str = re.sub(r"^data:\s*", "", line)
            if json_str and json_str != "[DONE]":
                return json.loads(json_str)

    raise RuntimeError(f"Could not parse MCP response: {trimmed[:200]}")
