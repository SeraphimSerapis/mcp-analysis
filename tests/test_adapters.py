"""Tests for adapter config parsing."""

from pathlib import Path

import pytest

from mcp_analysis.adapters.claude import ClaudeAdapter
from mcp_analysis.adapters.codex import CodexAdapter
from mcp_analysis.adapters.gemini import GeminiAdapter
from mcp_analysis.adapters.opencode import OpenCodeAdapter

FIXTURES = Path(__file__).parent / "fixtures"


# ─── OpenCode ──────────────────────────────────────────────────────────


class TestOpenCodeAdapter:
    @pytest.mark.asyncio
    async def test_detect(self):
        adapter = OpenCodeAdapter(FIXTURES / "opencode.jsonc")
        assert await adapter.detect() is True

    @pytest.mark.asyncio
    async def test_detect_no_mcp(self):
        adapter = OpenCodeAdapter(FIXTURES / "gemini-no-mcp.json")
        assert await adapter.detect() is False

    @pytest.mark.asyncio
    async def test_detect_missing(self):
        adapter = OpenCodeAdapter("/nonexistent/path.jsonc")
        assert await adapter.detect() is False

    @pytest.mark.asyncio
    async def test_parse_count(self):
        adapter = OpenCodeAdapter(FIXTURES / "opencode.jsonc")
        servers = await adapter.parse()
        assert len(servers) == 3

    @pytest.mark.asyncio
    async def test_parse_local(self):
        adapter = OpenCodeAdapter(FIXTURES / "opencode.jsonc")
        servers = await adapter.parse()
        local = next(s for s in servers if s.name == "local-tool")
        assert local.type == "local"
        assert local.command == ["node", "server.js"]
        assert local.enabled is True

    @pytest.mark.asyncio
    async def test_parse_remote(self):
        adapter = OpenCodeAdapter(FIXTURES / "opencode.jsonc")
        servers = await adapter.parse()
        remote = next(s for s in servers if s.name == "remote-tool")
        assert remote.type == "remote"
        assert remote.url == "https://example.com/mcp"

    @pytest.mark.asyncio
    async def test_parse_disabled(self):
        adapter = OpenCodeAdapter(FIXTURES / "opencode.jsonc")
        servers = await adapter.parse()
        disabled = next(s for s in servers if s.name == "disabled-tool")
        assert disabled.enabled is False


# ─── Gemini ────────────────────────────────────────────────────────────


class TestGeminiAdapter:
    @pytest.mark.asyncio
    async def test_detect(self):
        adapter = GeminiAdapter(FIXTURES / "gemini.json")
        assert await adapter.detect() is True

    @pytest.mark.asyncio
    async def test_detect_no_mcp(self):
        adapter = GeminiAdapter(FIXTURES / "gemini-no-mcp.json")
        assert await adapter.detect() is False

    @pytest.mark.asyncio
    async def test_parse_count(self):
        adapter = GeminiAdapter(FIXTURES / "gemini.json")
        servers = await adapter.parse()
        assert len(servers) == 4

    @pytest.mark.asyncio
    async def test_stdio_server(self):
        adapter = GeminiAdapter(FIXTURES / "gemini.json")
        servers = await adapter.parse()
        stdio = next(s for s in servers if s.name == "stdio-server")
        assert stdio.type == "local"
        assert stdio.command == ["node", "server.js"]

    @pytest.mark.asyncio
    async def test_sse_server(self):
        adapter = GeminiAdapter(FIXTURES / "gemini.json")
        servers = await adapter.parse()
        sse = next(s for s in servers if s.name == "sse-server")
        assert sse.type == "remote"
        assert sse.url == "https://example.com/sse"

    @pytest.mark.asyncio
    async def test_httpurl_server(self):
        adapter = GeminiAdapter(FIXTURES / "gemini.json")
        servers = await adapter.parse()
        http = next(s for s in servers if s.name == "http-server")
        assert http.type == "remote"
        assert http.url == "https://example.com/http"
        assert http.headers == {"X-Key": "test-value"}

    @pytest.mark.asyncio
    async def test_disabled(self):
        adapter = GeminiAdapter(FIXTURES / "gemini.json")
        servers = await adapter.parse()
        disabled = next(s for s in servers if s.name == "disabled-server")
        assert disabled.enabled is False


# ─── Claude ────────────────────────────────────────────────────────────


class TestClaudeAdapter:
    @pytest.mark.asyncio
    async def test_detect(self):
        adapter = ClaudeAdapter([FIXTURES / "claude.json"])
        assert await adapter.detect() is True

    @pytest.mark.asyncio
    async def test_detect_metadata_only(self):
        adapter = ClaudeAdapter([FIXTURES / "claude-metadata-only.json"])
        assert await adapter.detect() is False

    @pytest.mark.asyncio
    async def test_candidate_ordering(self):
        adapter = ClaudeAdapter([
            FIXTURES / "claude-metadata-only.json",
            FIXTURES / "claude.json",
        ])
        assert await adapter.detect() is True
        assert adapter.get_config_path() == str(FIXTURES / "claude.json")

    @pytest.mark.asyncio
    async def test_parse_count(self):
        adapter = ClaudeAdapter([FIXTURES / "claude.json"])
        servers = await adapter.parse()
        assert len(servers) == 3

    @pytest.mark.asyncio
    async def test_parse_local(self):
        adapter = ClaudeAdapter([FIXTURES / "claude.json"])
        servers = await adapter.parse()
        local = next(s for s in servers if s.name == "local-server")
        assert local.command == ["npx", "-y", "test-server"]
        assert local.environment == {"TOKEN": "abc"}

    @pytest.mark.asyncio
    async def test_parse_without_detect(self):
        adapter = ClaudeAdapter([FIXTURES / "claude.json"])
        servers = await adapter.parse()
        assert len(servers) == 3

    @pytest.mark.asyncio
    async def test_parse_no_config(self):
        adapter = ClaudeAdapter([FIXTURES / "claude-metadata-only.json"])
        servers = await adapter.parse()
        assert servers == []


# ─── Codex ─────────────────────────────────────────────────────────────


class TestCodexAdapter:
    @pytest.mark.asyncio
    async def test_detect(self):
        adapter = CodexAdapter(FIXTURES / "codex.toml")
        assert await adapter.detect() is True

    @pytest.mark.asyncio
    async def test_detect_missing(self):
        adapter = CodexAdapter("/nonexistent/config.toml")
        assert await adapter.detect() is False

    @pytest.mark.asyncio
    async def test_detect_no_mcp(self):
        adapter = CodexAdapter(FIXTURES / "codex-no-mcp.toml")
        assert await adapter.detect() is False

    @pytest.mark.asyncio
    async def test_parse_count(self):
        adapter = CodexAdapter(FIXTURES / "codex.toml")
        servers = await adapter.parse()
        assert len(servers) == 4

    @pytest.mark.asyncio
    async def test_local_server(self):
        adapter = CodexAdapter(FIXTURES / "codex.toml")
        servers = await adapter.parse()
        local = next(s for s in servers if s.name == "local_tool")
        assert local.type == "local"
        assert local.command == ["node", "server.js"]
        assert local.enabled is True

    @pytest.mark.asyncio
    async def test_disabled(self):
        adapter = CodexAdapter(FIXTURES / "codex.toml")
        servers = await adapter.parse()
        disabled = next(s for s in servers if s.name == "disabled_tool")
        assert disabled.enabled is False

    @pytest.mark.asyncio
    async def test_bearer_token(self, monkeypatch):
        monkeypatch.setenv("TEST_BEARER", "my-bearer-token")
        adapter = CodexAdapter(FIXTURES / "codex.toml")
        servers = await adapter.parse()
        remote = next(s for s in servers if s.name == "remote_tool")
        assert remote.headers["Authorization"] == "Bearer my-bearer-token"
        assert remote.headers["X-Region"] == "us-east-1"

    @pytest.mark.asyncio
    async def test_env_headers(self, monkeypatch):
        monkeypatch.setenv("TEST_AUTH_VAR", "auth-value-123")
        adapter = CodexAdapter(FIXTURES / "codex.toml")
        servers = await adapter.parse()
        env = next(s for s in servers if s.name == "env_headers_tool")
        assert env.headers == {"Authorization": "auth-value-123"}
