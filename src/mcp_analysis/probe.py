"""MCP server probe module.

Connects to local (stdio) and remote (HTTP) MCP servers,
calls tools/list, and returns the raw tool definitions.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from . import __version__
from .env import resolve_environment, resolve_headers
from .tokenizer import count_tokens
from .types import McpServerConfig, ServerResult, ToolAnalysis

# Number of retry attempts for transient remote failures.
_REMOTE_RETRIES = 1
_RETRY_BACKOFF_S = 1.0


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
    """Probe a remote MCP server with retry on transient failures.

    A single ``httpx.AsyncClient`` is shared across retry attempts so that
    the underlying connection pool is reused.
    """
    if not config.url:
        raise RuntimeError("No URL specified for remote server")

    last_error: Exception | None = None

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        for attempt in range(_REMOTE_RETRIES + 1):
            try:
                return await _probe_remote_once(config, client)
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_error = exc
                if attempt < _REMOTE_RETRIES:
                    await asyncio.sleep(_RETRY_BACKOFF_S)

    raise last_error  # type: ignore[misc]


async def _probe_remote_once(
    config: McpServerConfig,
    client: httpx.AsyncClient,
) -> list[ToolAnalysis]:
    # Note: config.url is guaranteed non-None by the caller (_probe_remote).

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        **resolve_headers(config.headers),
    }

    # Step 1: Initialize
    init_resp = await client.post(
        config.url,  # type: ignore[arg-type]
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
    init_resp.raise_for_status()

    session_id = init_resp.headers.get("mcp-session")

    # Step 2: List tools
    tool_headers = {**headers}
    if session_id:
        tool_headers["Mcp-Session"] = session_id

    tool_resp = await client.post(
        config.url,  # type: ignore[arg-type]
        headers=tool_headers,
        json={"jsonrpc": "2.0", "method": "tools/list", "id": 2},
    )
    tool_resp.raise_for_status()

    data = _parse_jsonrpc_response(tool_resp.text, expected_id=2)

    # Check for JSON-RPC error responses (e.g. method not found).
    if "error" in data:
        err = data["error"]
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        raise RuntimeError(f"MCP JSON-RPC error: {msg}")

    # Guard against result: null (valid JSON-RPC but no tools payload).
    result_data = data.get("result")
    if result_data is None:
        result_data = {}
    tools: list[dict[str, Any]] = result_data.get("tools", [])
    return [_tool_to_analysis(t) for t in tools]


# ─── Helpers ───────────────────────────────────────────────────────────


def _tool_to_analysis(tool: Any) -> ToolAnalysis:
    """Convert an MCP tool (dict or pydantic model) to ToolAnalysis."""
    if hasattr(tool, "model_dump"):
        d: dict[str, Any] = tool.model_dump()
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


def _parse_jsonrpc_response(text: str, expected_id: int | None = None) -> dict:  # type: ignore[type-arg]
    """Parse a JSON-RPC response that may be plain JSON or SSE-wrapped.

    When *expected_id* is given, SSE streams are searched for the data event
    whose JSON-RPC ``id`` field matches — this prevents returning the wrong
    response when the server batches multiple events in a single stream.
    """
    trimmed = text.strip()
    if trimmed.startswith("{") or trimmed.startswith("["):
        result: dict = json.loads(trimmed)
        return result

    # SSE format: look for a "data:" line whose JSON-RPC id matches.
    # Fall back to the last non-[DONE] data line if no id match is found.
    fallback: dict | None = None
    for line in reversed(trimmed.split("\n")):
        line = line.strip()
        if not line.startswith("data:"):
            continue
        json_str = re.sub(r"^data:\s*", "", line)
        if not json_str or json_str == "[DONE]":
            continue
        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError:
            continue
        if expected_id is not None and parsed.get("id") == expected_id:
            return parsed  # type: ignore[no-any-return]
        if fallback is None:
            fallback = parsed

    if fallback is not None:
        return fallback

    raise RuntimeError(f"Could not parse MCP response: {trimmed[:200]}")
