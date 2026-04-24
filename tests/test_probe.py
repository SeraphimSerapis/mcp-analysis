"""Tests for probe module — _tool_to_analysis, probe_server (mocked), remote retry logic."""

from __future__ import annotations

import json
from dataclasses import dataclass
from unittest.mock import patch

import pytest

from mcp_analysis.probe import (
    _parse_jsonrpc_response,
    _probe_remote,
    _tool_to_analysis,
    probe_server,
)
from mcp_analysis.types import McpServerConfig

# ─── _tool_to_analysis ────────────────────────────────────────────────


class TestToolToAnalysis:
    def test_dict_input(self):
        tool = {"name": "search", "description": "Search the web", "inputSchema": {}}
        result = _tool_to_analysis(tool)
        assert result.name == "search"
        assert result.description == "Search the web"
        assert result.char_count == len(json.dumps(tool))

    def test_pydantic_model_input(self):
        """Tools from the MCP SDK come as pydantic models with model_dump()."""

        @dataclass
        class FakeTool:
            name: str
            description: str

            def model_dump(self) -> dict:
                return {"name": self.name, "description": self.description}

        tool = FakeTool(name="code_review", description="Review code")
        result = _tool_to_analysis(tool)
        assert result.name == "code_review"
        assert result.description == "Review code"

    def test_fallback_for_unknown_type(self):
        result = _tool_to_analysis("unexpected_string_tool")
        assert result.name == "unexpected_string_tool"
        assert result.char_count > 0

    def test_missing_name_key(self):
        result = _tool_to_analysis({"description": "orphaned tool"})
        assert result.name == "unknown"

    def test_missing_description_key(self):
        result = _tool_to_analysis({"name": "nameless"})
        assert result.description == ""

    def test_empty_dict(self):
        result = _tool_to_analysis({})
        assert result.name == "unknown"
        assert result.description == ""
        assert result.char_count == len("{}")

    def test_raw_json_is_valid(self):
        tool = {"name": "t", "description": "d", "extra": [1, 2, 3]}
        result = _tool_to_analysis(tool)
        parsed = json.loads(result.raw_json)
        assert parsed == tool


# ─── probe_server (integration with mocked transport) ─────────────────


class TestProbeServer:
    @pytest.mark.asyncio
    async def test_local_server_no_command(self):
        """Local server without command raises and returns error."""
        config = McpServerConfig(name="broken", type="local", command=None)
        result = await probe_server(config, timeout_s=5.0)
        assert result.error is not None
        assert "No command" in result.error

    @pytest.mark.asyncio
    async def test_remote_server_no_url(self):
        """Remote server without URL raises and returns error."""
        config = McpServerConfig(name="broken", type="remote", url=None)
        result = await probe_server(config, timeout_s=5.0)
        assert result.error is not None
        assert "No URL" in result.error

    @pytest.mark.asyncio
    async def test_error_truncated_to_200_chars(self):
        """Long error messages are truncated."""
        config = McpServerConfig(name="broken", type="local", command=None)

        long_error = "x" * 500
        with patch("mcp_analysis.probe._probe_local", side_effect=RuntimeError(long_error)):
            result = await probe_server(config, timeout_s=5.0)

        assert len(result.error) <= 200

    @pytest.mark.asyncio
    async def test_successful_probe_aggregates_tokens(self):
        """Successful probe populates tools, chars, and tokens."""
        config = McpServerConfig(name="good-server", type="local", command=["node", "s.js"])

        fake_tools = [
            {"name": "tool1", "description": "desc1"},
            {"name": "tool2", "description": "desc2"},
        ]

        async def fake_probe_local(cfg, timeout):
            return [_tool_to_analysis(t) for t in fake_tools]

        with patch("mcp_analysis.probe._probe_local", side_effect=fake_probe_local):
            result = await probe_server(config, timeout_s=5.0)

        assert result.error is None
        assert len(result.tools) == 2
        assert result.total_chars > 0
        assert result.estimated_tokens > 0


# ─── _probe_remote retry logic ────────────────────────────────────────


class TestProbeRemoteRetry:
    @pytest.mark.asyncio
    async def test_retries_on_transport_error(self):
        """Transient transport errors trigger a retry."""
        import httpx

        config = McpServerConfig(name="flaky", type="remote", url="https://example.com/mcp")
        call_count = 0

        async def counting_probe(cfg, client):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.TransportError("Connection reset")
            return [_tool_to_analysis({"name": "recovered"})]

        with patch("mcp_analysis.probe._probe_remote_once", side_effect=counting_probe), \
             patch("mcp_analysis.probe._RETRY_BACKOFF_S", 0):  # no wait
            result = await _probe_remote(config, timeout_s=5.0)

        assert call_count == 2
        assert len(result) == 1
        assert result[0].name == "recovered"

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        """After exhausting retries, the last error is raised."""
        import httpx

        config = McpServerConfig(name="dead", type="remote", url="https://example.com/mcp")

        async def always_fail(cfg, client):
            raise httpx.TransportError("Connection refused")

        with patch("mcp_analysis.probe._probe_remote_once", side_effect=always_fail), \
             patch("mcp_analysis.probe._RETRY_BACKOFF_S", 0), \
             pytest.raises(httpx.TransportError, match="Connection refused"):
            await _probe_remote(config, timeout_s=5.0)

    @pytest.mark.asyncio
    async def test_non_transport_errors_not_retried(self):
        """Non-transport errors (like ValueError) are not caught by retry."""
        config = McpServerConfig(name="bad", type="remote", url="https://example.com/mcp")

        async def value_error(cfg, client):
            raise ValueError("Bad data")

        with patch("mcp_analysis.probe._probe_remote_once", side_effect=value_error):
            result = await probe_server(config, timeout_s=5.0)

        # The error should be caught by probe_server's outer try/except
        assert result.error is not None
        assert "Bad data" in result.error


# ─── _parse_jsonrpc_response — additional edge cases ──────────────────


class TestParseJsonrpcResponseEdgeCases:
    def test_sse_with_id_matching(self):
        """When expected_id is given, returns the matching event."""
        text = (
            'data: {"jsonrpc": "2.0", "result": {"type": "init"}, "id": 1}\n'
            'data: {"jsonrpc": "2.0", "result": {"tools": [{"name": "target"}]}, "id": 2}\n'
        )
        result = _parse_jsonrpc_response(text, expected_id=2)
        assert result["result"]["tools"][0]["name"] == "target"

    def test_sse_falls_back_to_last_event_without_id_match(self):
        """Without matching ID, returns the last parseable event."""
        text = (
            'data: {"jsonrpc": "2.0", "result": {"x": 1}, "id": 99}\n'
            'data: {"jsonrpc": "2.0", "result": {"x": 2}, "id": 98}\n'
        )
        result = _parse_jsonrpc_response(text, expected_id=777)
        # Falls back — the reversed iteration picks the first one scanned (id=98)
        assert result is not None

    def test_json_array_response(self):
        """JSON-RPC batch response (array) is returned as-is."""
        text = '[{"jsonrpc": "2.0", "result": {}, "id": 1}]'
        result = _parse_jsonrpc_response(text)
        assert isinstance(result, list)

    def test_sse_skips_invalid_json_lines(self):
        """Invalid JSON in SSE data lines is silently skipped."""
        text = (
            'data: not-valid-json\n'
            'data: {"jsonrpc": "2.0", "result": {"ok": true}, "id": 1}\n'
        )
        result = _parse_jsonrpc_response(text, expected_id=1)
        assert result["result"]["ok"] is True
