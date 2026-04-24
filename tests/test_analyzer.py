"""Tests for the analyzer module — orchestration, aggregation, and edge cases."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from mcp_analysis.adapters.base import ConfigAdapter
from mcp_analysis.analyzer import _MAX_CONCURRENT_PROBES, analyze_adapter, build_report
from mcp_analysis.types import CliAnalysis, CliOptions, McpServerConfig, ServerResult, ToolAnalysis

# ─── Helpers ───────────────────────────────────────────────────────────


class FakeAdapter(ConfigAdapter):
    """A fake adapter for testing without file I/O."""

    def __init__(
        self,
        servers: list[McpServerConfig] | None = None,
        name: str = "FakeCLI",
        slug: str = "fakecli",
    ):
        self._servers = servers or []
        self._name = name
        self._slug = slug

    @property
    def name(self) -> str:
        return self._name

    @property
    def slug(self) -> str:
        return self._slug

    def get_config_path(self) -> str:
        return "/fake/config.json"

    async def detect(self) -> bool:
        return True

    async def parse(self) -> list[McpServerConfig]:
        return self._servers


def _local_server(name: str = "local-srv", enabled: bool = True) -> McpServerConfig:
    return McpServerConfig(
        name=name,
        type="local",
        command=["node", "server.js"],
        enabled=enabled,
    )


def _remote_server(name: str = "remote-srv", enabled: bool = True) -> McpServerConfig:
    return McpServerConfig(
        name=name,
        type="remote",
        url="https://example.com/mcp",
        enabled=enabled,
    )


def _mock_probe_result(config: McpServerConfig, **kwargs) -> ServerResult:
    """Create a successful ServerResult matching a config."""
    return ServerResult(
        name=config.name,
        type=config.type,
        tools=[ToolAnalysis(name="t1", description="d", char_count=100, raw_json="{}")],
        total_chars=100,
        estimated_tokens=25,
        **kwargs,
    )


def _options(**overrides) -> CliOptions:
    defaults = dict(all=True, timeout=5.0)
    defaults.update(overrides)
    return CliOptions(**defaults)


# ─── analyze_adapter ──────────────────────────────────────────────────


class TestAnalyzeAdapter:
    @pytest.mark.asyncio
    async def test_empty_servers(self):
        """Adapter with no servers returns an empty CliAnalysis."""
        adapter = FakeAdapter(servers=[])
        result = await analyze_adapter(adapter, _options())
        assert result.total_tools == 0
        assert result.servers == []
        assert result.disabled_server_count == 0

    @pytest.mark.asyncio
    async def test_all_disabled(self):
        """All servers disabled → empty result with disabled count."""
        adapter = FakeAdapter(servers=[
            _local_server("a", enabled=False),
            _local_server("b", enabled=False),
        ])
        result = await analyze_adapter(adapter, _options())
        assert result.total_tools == 0
        assert result.disabled_server_count == 2

    @pytest.mark.asyncio
    async def test_skip_local(self):
        """--skip-local skips local servers, probes remote ones."""
        adapter = FakeAdapter(servers=[
            _local_server("local-1"),
            _remote_server("remote-1"),
        ])

        async def fake_probe(config, timeout):
            return _mock_probe_result(config)

        with patch("mcp_analysis.analyzer.probe_server", side_effect=fake_probe):
            result = await analyze_adapter(adapter, _options(skip_local=True))

        assert len(result.servers) == 1
        assert result.servers[0].name == "remote-1"

    @pytest.mark.asyncio
    async def test_probes_enabled_servers(self):
        """Only enabled servers are probed."""
        adapter = FakeAdapter(servers=[
            _local_server("enabled"),
            _local_server("disabled", enabled=False),
        ])

        async def fake_probe(config, timeout):
            return _mock_probe_result(config)

        with patch("mcp_analysis.analyzer.probe_server", side_effect=fake_probe):
            result = await analyze_adapter(adapter, _options())

        assert len(result.servers) == 1
        assert result.servers[0].name == "enabled"
        assert result.disabled_server_count == 1

    @pytest.mark.asyncio
    async def test_probe_error_included_in_results(self):
        """Server probe errors are captured, not raised."""
        adapter = FakeAdapter(servers=[_local_server("broken")])

        async def failing_probe(config, timeout):
            return ServerResult(name=config.name, type=config.type, error="Connection refused")

        with patch("mcp_analysis.analyzer.probe_server", side_effect=failing_probe):
            result = await analyze_adapter(adapter, _options())

        assert len(result.servers) == 1
        assert result.servers[0].error == "Connection refused"
        assert result.total_tools == 0

    @pytest.mark.asyncio
    async def test_token_aggregation(self):
        """Total tokens are correctly aggregated across servers."""
        adapter = FakeAdapter(servers=[
            _local_server("s1"),
            _local_server("s2"),
        ])

        call_count = 0

        async def counting_probe(config, timeout):
            nonlocal call_count
            call_count += 1
            return ServerResult(
                name=config.name,
                type=config.type,
                tools=[ToolAnalysis(name="t", description="", char_count=40, raw_json="{}")],
                total_chars=40,
                estimated_tokens=10,
            )

        with patch("mcp_analysis.analyzer.probe_server", side_effect=counting_probe):
            result = await analyze_adapter(adapter, _options())

        assert call_count == 2
        assert result.total_tools == 2
        assert result.total_estimated_tokens == 20

    @pytest.mark.asyncio
    async def test_concurrent_probing(self):
        """Multiple servers are probed concurrently (not sequentially)."""
        import asyncio

        # Track concurrent execution
        currently_running = 0
        max_concurrent = 0

        servers = [_local_server(f"srv-{i}") for i in range(8)]
        adapter = FakeAdapter(servers=servers)

        async def slow_probe(config, timeout):
            nonlocal currently_running, max_concurrent
            currently_running += 1
            max_concurrent = max(max_concurrent, currently_running)
            await asyncio.sleep(0.01)
            currently_running -= 1
            return _mock_probe_result(config)

        with patch("mcp_analysis.analyzer.probe_server", side_effect=slow_probe):
            result = await analyze_adapter(adapter, _options())

        # Should have run concurrently up to the semaphore limit
        assert max_concurrent > 1
        assert max_concurrent <= _MAX_CONCURRENT_PROBES
        assert len(result.servers) == 8


# ─── build_report ─────────────────────────────────────────────────────


class TestBuildReport:
    def test_empty_analyses(self):
        report = build_report([])
        assert report.total_tools == 0
        assert report.total_estimated_tokens == 0
        assert report.total_exact_tokens is None
        assert report.timestamp != ""

    def test_single_cli(self):
        analysis = CliAnalysis(
            cli="TestCLI",
            slug="testcli",
            config_path="/path",
            total_tools=5,
            total_estimated_tokens=1000,
        )
        report = build_report([analysis])
        assert report.total_tools == 5
        assert report.total_estimated_tokens == 1000

    def test_multiple_clis(self):
        a1 = CliAnalysis(cli="A", slug="a", config_path="/a", total_tools=3, total_estimated_tokens=500)
        a2 = CliAnalysis(cli="B", slug="b", config_path="/b", total_tools=7, total_estimated_tokens=1500)
        report = build_report([a1, a2])
        assert report.total_tools == 10
        assert report.total_estimated_tokens == 2000

    def test_exact_tokens_none_when_no_cli_has_exact(self):
        a = CliAnalysis(cli="A", slug="a", config_path="/a", total_exact_tokens=None)
        report = build_report([a])
        assert report.total_exact_tokens is None

    def test_exact_tokens_summed_when_available(self):
        a1 = CliAnalysis(cli="A", slug="a", config_path="/a", total_exact_tokens=100)
        a2 = CliAnalysis(cli="B", slug="b", config_path="/b", total_exact_tokens=200)
        report = build_report([a1, a2])
        assert report.total_exact_tokens == 300

    def test_mixed_exact_tokens(self):
        """When some CLIs have exact tokens and some don't, sums the available ones."""
        a1 = CliAnalysis(cli="A", slug="a", config_path="/a", total_exact_tokens=100)
        a2 = CliAnalysis(cli="B", slug="b", config_path="/b", total_exact_tokens=None)
        report = build_report([a1, a2])
        assert report.total_exact_tokens == 100

    def test_timestamp_populated(self):
        report = build_report([])
        assert "T" in report.timestamp  # ISO format
