"""Shared test fixtures for mcp-analysis."""

from __future__ import annotations

from pathlib import Path

from mcp_analysis.types import (
    CliAnalysis,
    FullReport,
    ServerResult,
    ToolAnalysis,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ─── ToolAnalysis factories ────────────────────────────────────────────


def make_tool(name: str = "test-tool", description: str = "A test tool", char_count: int = 100) -> ToolAnalysis:
    """Create a minimal ToolAnalysis for testing."""
    return ToolAnalysis(
        name=name,
        description=description,
        char_count=char_count,
        raw_json=f'{{"name": "{name}", "description": "{description}"}}',
    )


# ─── ServerResult factories ───────────────────────────────────────────


def make_server(
    name: str = "test-server",
    type: str = "local",
    tools: list[ToolAnalysis] | None = None,
    total_chars: int = 0,
    estimated_tokens: int = 0,
    exact_tokens: int | None = None,
    error: str | None = None,
) -> ServerResult:
    """Create a ServerResult for testing."""
    if tools is None:
        tools = [make_tool()]
        total_chars = total_chars or 100
        estimated_tokens = estimated_tokens or 25
    return ServerResult(
        name=name,
        type=type,
        tools=tools,
        total_chars=total_chars,
        estimated_tokens=estimated_tokens,
        exact_tokens=exact_tokens,
        error=error,
    )


def make_server_error(name: str = "broken-server", error: str = "Connection refused") -> ServerResult:
    """Create a ServerResult representing a probe failure."""
    return ServerResult(name=name, type="local", error=error)


# ─── CliAnalysis factories ────────────────────────────────────────────


def make_cli_analysis(
    cli: str = "TestCLI",
    slug: str = "testcli",
    servers: list[ServerResult] | None = None,
    disabled_server_count: int = 0,
) -> CliAnalysis:
    """Create a CliAnalysis for testing."""
    if servers is None:
        servers = [make_server()]
    total_tools = sum(len(s.tools) for s in servers)
    total_est = sum(s.estimated_tokens for s in servers)
    return CliAnalysis(
        cli=cli,
        slug=slug,
        config_path="/home/user/.test/config.json",
        servers=servers,
        total_tools=total_tools,
        total_estimated_tokens=total_est,
        disabled_server_count=disabled_server_count,
    )


# ─── FullReport factories ─────────────────────────────────────────────


def make_report(
    analyses: list[CliAnalysis] | None = None,
    timestamp: str = "2026-01-01T00:00:00.000Z",
) -> FullReport:
    """Create a FullReport for testing."""
    if analyses is None:
        analyses = [make_cli_analysis()]
    total_tools = sum(a.total_tools for a in analyses)
    total_est = sum(a.total_estimated_tokens for a in analyses)
    return FullReport(
        analyses=analyses,
        total_tools=total_tools,
        total_estimated_tokens=total_est,
        timestamp=timestamp,
    )
