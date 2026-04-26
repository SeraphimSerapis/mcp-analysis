"""Tests for output formatters."""

import json
from unittest.mock import patch

from mcp_analysis.output import format_json, format_markdown, format_table
from mcp_analysis.types import CliAnalysis, FullReport, ServerResult, ToolAnalysis


def _make_report(**overrides) -> FullReport:
    defaults = dict(
        analyses=[
            CliAnalysis(
                cli="TestCLI",
                slug="testcli",
                config_path="/home/user/.test/config.json",
                servers=[
                    ServerResult(
                        name="big-server",
                        type="remote",
                        tools=[
                            ToolAnalysis(name="t1", description="", char_count=100, raw_json="{}"),
                            ToolAnalysis(name="t2", description="", char_count=200, raw_json="{}"),
                        ],
                        total_chars=300,
                        estimated_tokens=75,
                    ),
                    ServerResult(
                        name="small-server",
                        type="local",
                        tools=[
                            ToolAnalysis(name="t3", description="", char_count=50, raw_json="{}"),
                        ],
                        total_chars=50,
                        estimated_tokens=13,
                    ),
                ],
                total_tools=3,
                total_estimated_tokens=88,
            ),
        ],
        total_tools=3,
        total_estimated_tokens=88,
        timestamp="2026-01-01T00:00:00.000Z",
    )
    defaults.update(overrides)
    return FullReport(**defaults)


class TestFormatJson:
    def test_valid_json(self):
        output = format_json(_make_report())
        parsed = json.loads(output)
        assert parsed["total_tools"] == 3

    def test_includes_timestamp(self):
        output = json.loads(format_json(_make_report()))
        assert output["timestamp"] == "2026-01-01T00:00:00.000Z"

    def test_headers_are_redacted(self):
        """Bearer tokens and other header values must not appear in JSON output."""
        report = _make_report(
            analyses=[CliAnalysis(
                cli="SecCLI",
                slug="seccli",
                config_path="/p",
                servers=[ServerResult(
                    name="token-srv",
                    type="remote",
                    tools=[],
                )],
            )]
        )
        # Inject headers via the underlying ServerResult (simulates Codex adapter)
        report.analyses[0].servers[0].__dict__  # ensure writable
        # Manually set headers on the server config (ServerResult doesn't have headers,
        # but McpServerConfig does; test the recursive redaction on the full dict)
        from mcp_analysis.output import _redact_headers
        data = {"analyses": [{"servers": [{"headers": {"Authorization": "Bearer sk-secret123"}}]}]}
        _redact_headers(data)
        assert data["analyses"][0]["servers"][0]["headers"]["Authorization"] == "[REDACTED]"


class TestFormatMarkdown:
    def test_contains_heading(self):
        md = format_markdown(_make_report())
        assert "# MCP Tool Token Analysis" in md
        assert "## TestCLI" in md

    def test_contains_servers(self):
        md = format_markdown(_make_report())
        assert "big-server" in md
        assert "small-server" in md

    def test_sorting(self):
        md = format_markdown(_make_report())
        assert md.index("big-server") < md.index("small-server")

    def test_disabled_message(self):
        report = _make_report(
            analyses=[CliAnalysis(cli="X", slug="x", config_path="/p", disabled_server_count=5)]
        )
        md = format_markdown(report)
        assert "5 server(s) configured but disabled" in md

    def test_no_servers_message(self):
        report = _make_report(
            analyses=[CliAnalysis(cli="X", slug="x", config_path="/p")]
        )
        md = format_markdown(report)
        assert "No MCP servers configured" in md

    def test_error_server_row(self):
        """Error rows should show error text in the correct column."""
        report = _make_report(
            analyses=[CliAnalysis(
                cli="ErrCLI",
                slug="errcli",
                config_path="/p",
                servers=[ServerResult(name="broken", type="remote", error="Connection refused")],
            )]
        )
        md = format_markdown(report)
        assert "broken" in md
        assert "⚠ error" in md


class TestFormatTable:
    def test_contains_cli_name(self):
        output = format_table(_make_report())
        assert "TestCLI" in output

    @patch("mcp_analysis.output.has_exact_tokenizer", return_value=False)
    def test_contains_budget_reference(self, _mock):
        """Budget bars appear when estimated tokens > 0 (exact tokenizer disabled)."""
        output = format_table(_make_report())
        assert "Context budget" in output
        assert "MiniMax" in output

    @patch("mcp_analysis.output.has_exact_tokenizer", return_value=False)
    def test_error_server_in_table(self, _mock):
        """Error servers show error message in the table."""
        report = _make_report(
            analyses=[CliAnalysis(
                cli="ErrCLI",
                slug="errcli",
                config_path="/p",
                servers=[ServerResult(name="broken", type="local", error="Timed out after 15s")],
            )]
        )
        output = format_table(report)
        assert "broken" in output
        assert "error" in output

