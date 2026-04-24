"""Tests for CLI entry point using Click's CliRunner."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from mcp_analysis.cli import main
from mcp_analysis.types import CliAnalysis, ServerResult, ToolAnalysis

FIXTURES = Path(__file__).parent / "fixtures"


def _make_analysis(cli: str = "TestCLI", slug: str = "testcli") -> CliAnalysis:
    return CliAnalysis(
        cli=cli,
        slug=slug,
        config_path="/test/config.json",
        servers=[
            ServerResult(
                name="mock-server",
                type="local",
                tools=[ToolAnalysis(name="t1", description="d", char_count=100, raw_json="{}")],
                total_chars=100,
                estimated_tokens=25,
            )
        ],
        total_tools=1,
        total_estimated_tokens=25,
    )


class TestCliVersion:
    def test_version_flag(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help_flag(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Analyze MCP tool token consumption" in result.output
        assert "--opencode" in result.output
        assert "--gemini" in result.output
        assert "--claude" in result.output
        assert "--codex" in result.output


class TestCliNoConfig:
    def test_exits_when_no_configs_found(self):
        """When no CLI configs are detected, exit code 1."""
        runner = CliRunner()

        with patch("mcp_analysis.cli.get_all_adapters") as mock_adapters:
            mock_adapter = AsyncMock()
            mock_adapter.name = "FakeCLI"
            mock_adapter.slug = "fakecli"
            mock_adapter.detect = AsyncMock(return_value=False)
            mock_adapter.get_config_path = lambda: "/fake/path"
            mock_adapters.return_value = [mock_adapter]

            result = runner.invoke(main, [])

        assert result.exit_code == 1


class TestCliJsonOutput:
    def test_json_output(self):
        """--json flag produces valid JSON output."""
        import json as jsonmod

        runner = CliRunner()

        with patch("mcp_analysis.cli.get_all_adapters") as mock_adapters, \
             patch("mcp_analysis.cli.analyze_adapter") as mock_analyze:

            mock_adapter = AsyncMock()
            mock_adapter.name = "TestCLI"
            mock_adapter.slug = "testcli"
            mock_adapter.detect = AsyncMock(return_value=True)
            mock_adapter.get_config_path = lambda: "/test/path"
            mock_adapters.return_value = [mock_adapter]

            mock_analyze.return_value = _make_analysis()

            result = runner.invoke(main, ["--json", "--no-tokenizer"])

        assert result.exit_code == 0
        # CliRunner mixes stdout and stderr; extract the JSON block.
        output = result.output
        json_start = output.index("{")
        json_text = output[json_start:]
        parsed = jsonmod.loads(json_text)
        assert parsed["total_tools"] == 1



class TestCliMarkdownOutput:
    def test_markdown_output(self):
        """--markdown flag produces markdown output."""
        runner = CliRunner()

        with patch("mcp_analysis.cli.get_all_adapters") as mock_adapters, \
             patch("mcp_analysis.cli.analyze_adapter") as mock_analyze:

            mock_adapter = AsyncMock()
            mock_adapter.name = "TestCLI"
            mock_adapter.slug = "testcli"
            mock_adapter.detect = AsyncMock(return_value=True)
            mock_adapter.get_config_path = lambda: "/test/path"
            mock_adapters.return_value = [mock_adapter]

            mock_analyze.return_value = _make_analysis()

            result = runner.invoke(main, ["--markdown", "--no-tokenizer"])

        assert result.exit_code == 0
        assert "# MCP Tool Token Analysis" in result.output
        assert "TestCLI" in result.output


class TestCliTableOutput:
    def test_table_output_default(self):
        """Default output is a rich table."""
        runner = CliRunner()

        with patch("mcp_analysis.cli.get_all_adapters") as mock_adapters, \
             patch("mcp_analysis.cli.analyze_adapter") as mock_analyze:

            mock_adapter = AsyncMock()
            mock_adapter.name = "TestCLI"
            mock_adapter.slug = "testcli"
            mock_adapter.detect = AsyncMock(return_value=True)
            mock_adapter.get_config_path = lambda: "/test/path"
            mock_adapters.return_value = [mock_adapter]

            mock_analyze.return_value = _make_analysis()

            result = runner.invoke(main, ["--no-tokenizer"])

        assert result.exit_code == 0
        assert "TestCLI" in result.output


class TestCliSpecificAdapter:
    def test_specific_flag_disables_all(self):
        """Passing --opencode should not auto-detect other CLIs."""
        runner = CliRunner()

        with patch("mcp_analysis.cli.get_all_adapters") as mock_adapters, \
             patch("mcp_analysis.cli.analyze_adapter") as mock_analyze:

            opencode = AsyncMock()
            opencode.name = "OpenCode"
            opencode.slug = "opencode"
            opencode.detect = AsyncMock(return_value=True)
            opencode.get_config_path = lambda: "/opencode/path"

            gemini = AsyncMock()
            gemini.name = "Gemini CLI"
            gemini.slug = "gemini"
            gemini.detect = AsyncMock(return_value=True)
            gemini.get_config_path = lambda: "/gemini/path"

            mock_adapters.return_value = [opencode, gemini]
            mock_analyze.return_value = _make_analysis(cli="OpenCode", slug="opencode")

            result = runner.invoke(main, ["--opencode", "--no-tokenizer", "--json"])

        # Only OpenCode should be analyzed, not Gemini
        assert result.exit_code == 0
        # detect() should be called for OpenCode but not necessarily for Gemini
        # since --all is disabled

    def test_missing_specific_config_warns(self):
        """Requesting a specific CLI that isn't configured shows a warning."""
        runner = CliRunner()

        with patch("mcp_analysis.cli.get_all_adapters") as mock_adapters:
            mock_adapter = AsyncMock()
            mock_adapter.name = "OpenCode"
            mock_adapter.slug = "opencode"
            mock_adapter.detect = AsyncMock(return_value=False)
            mock_adapter.get_config_path = lambda: "/opencode/path"
            mock_adapters.return_value = [mock_adapter]

            result = runner.invoke(main, ["--opencode", "--no-tokenizer"])

        # Should exit with error since no configs found
        assert result.exit_code == 1


class TestCliSkipLocal:
    def test_skip_local_flag(self):
        """--skip-local is passed through to options correctly."""
        runner = CliRunner()

        with patch("mcp_analysis.cli.get_all_adapters") as mock_adapters, \
             patch("mcp_analysis.cli.analyze_adapter") as mock_analyze:

            mock_adapter = AsyncMock()
            mock_adapter.name = "TestCLI"
            mock_adapter.slug = "testcli"
            mock_adapter.detect = AsyncMock(return_value=True)
            mock_adapter.get_config_path = lambda: "/test/path"
            mock_adapters.return_value = [mock_adapter]

            mock_analyze.return_value = _make_analysis()

            result = runner.invoke(main, ["--skip-local", "--no-tokenizer", "--json"])

        assert result.exit_code == 0
        # Verify analyze_adapter was called with skip_local=True
        call_args = mock_analyze.call_args
        options = call_args[0][1]
        assert options.skip_local is True


class TestCliTimeout:
    def test_custom_timeout(self):
        """--timeout is passed through to options."""
        runner = CliRunner()

        with patch("mcp_analysis.cli.get_all_adapters") as mock_adapters, \
             patch("mcp_analysis.cli.analyze_adapter") as mock_analyze:

            mock_adapter = AsyncMock()
            mock_adapter.name = "TestCLI"
            mock_adapter.slug = "testcli"
            mock_adapter.detect = AsyncMock(return_value=True)
            mock_adapter.get_config_path = lambda: "/test/path"
            mock_adapters.return_value = [mock_adapter]

            mock_analyze.return_value = _make_analysis()

            result = runner.invoke(main, ["--timeout", "30", "--no-tokenizer", "--json"])

        assert result.exit_code == 0
        call_args = mock_analyze.call_args
        options = call_args[0][1]
        assert options.timeout == 30.0


class TestCliAnalyzerException:
    def test_adapter_exception_doesnt_crash(self):
        """If analyze_adapter raises, the CLI logs the error and continues."""
        runner = CliRunner()

        with patch("mcp_analysis.cli.get_all_adapters") as mock_adapters, \
             patch("mcp_analysis.cli.analyze_adapter") as mock_analyze:

            mock_adapter = AsyncMock()
            mock_adapter.name = "TestCLI"
            mock_adapter.slug = "testcli"
            mock_adapter.detect = AsyncMock(return_value=True)
            mock_adapter.get_config_path = lambda: "/test/path"
            mock_adapters.return_value = [mock_adapter]

            mock_analyze.side_effect = RuntimeError("Adapter crashed")

            result = runner.invoke(main, ["--no-tokenizer", "--json"])

        # Should not crash — outputs an empty report
        assert result.exit_code == 0


class TestCliDryRun:
    def test_dry_run_shows_servers(self):
        """--dry-run prints server info without probing."""
        from mcp_analysis.types import McpServerConfig

        runner = CliRunner()

        with patch("mcp_analysis.cli.get_all_adapters") as mock_adapters:
            mock_adapter = AsyncMock()
            mock_adapter.name = "TestCLI"
            mock_adapter.slug = "testcli"
            mock_adapter.detect = AsyncMock(return_value=True)
            mock_adapter.get_config_path = lambda: "/test/path"
            mock_adapter.parse = AsyncMock(return_value=[
                McpServerConfig(name="local-srv", type="local", command=["node", "s.js"]),
                McpServerConfig(name="remote-srv", type="remote", url="https://example.com/mcp"),
                McpServerConfig(name="disabled-srv", type="local", command=["x"], enabled=False),
            ])
            mock_adapters.return_value = [mock_adapter]

            result = runner.invoke(main, ["--dry-run"])

        assert result.exit_code == 0
        output = result.output
        assert "local-srv" in output
        assert "remote-srv" in output
        assert "example.com/mcp" in output
        assert "1 additional server(s) disabled" in output

    def test_dry_run_skips_tokenizer(self):
        """--dry-run should not initialize the tokenizer."""
        runner = CliRunner()

        with patch("mcp_analysis.cli.get_all_adapters") as mock_adapters, \
             patch("mcp_analysis.cli.init_tokenizer") as mock_tokenizer:

            mock_adapter = AsyncMock()
            mock_adapter.name = "TestCLI"
            mock_adapter.slug = "testcli"
            mock_adapter.detect = AsyncMock(return_value=True)
            mock_adapter.get_config_path = lambda: "/test/path"
            mock_adapter.parse = AsyncMock(return_value=[])
            mock_adapters.return_value = [mock_adapter]

            runner.invoke(main, ["--dry-run"])

        # Tokenizer should never be called in dry-run mode
        mock_tokenizer.assert_not_called()

    def test_dry_run_skip_local_marker(self):
        """--dry-run --skip-local marks local servers as skipped."""
        from mcp_analysis.types import McpServerConfig

        runner = CliRunner()

        with patch("mcp_analysis.cli.get_all_adapters") as mock_adapters:
            mock_adapter = AsyncMock()
            mock_adapter.name = "TestCLI"
            mock_adapter.slug = "testcli"
            mock_adapter.detect = AsyncMock(return_value=True)
            mock_adapter.get_config_path = lambda: "/test/path"
            mock_adapter.parse = AsyncMock(return_value=[
                McpServerConfig(name="local-srv", type="local", command=["node", "s.js"]),
            ])
            mock_adapters.return_value = [mock_adapter]

            result = runner.invoke(main, ["--dry-run", "--skip-local"])

        assert result.exit_code == 0
        assert "skip-local" in result.output

    def test_help_shows_dry_run(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert "--dry-run" in result.output


class TestCliExitCodes:
    def test_exit_2_when_all_probes_fail(self):
        """Exit code 2 when all probes returned errors."""
        from mcp_analysis.types import ServerResult

        runner = CliRunner()

        with patch("mcp_analysis.cli.get_all_adapters") as mock_adapters, \
             patch("mcp_analysis.cli.analyze_adapter") as mock_analyze:

            mock_adapter = AsyncMock()
            mock_adapter.name = "TestCLI"
            mock_adapter.slug = "testcli"
            mock_adapter.detect = AsyncMock(return_value=True)
            mock_adapter.get_config_path = lambda: "/test/path"
            mock_adapters.return_value = [mock_adapter]

            mock_analyze.return_value = CliAnalysis(
                cli="TestCLI",
                slug="testcli",
                config_path="/test/path",
                servers=[
                    ServerResult(name="broken-1", type="local", error="Timeout"),
                    ServerResult(name="broken-2", type="remote", error="Connection refused"),
                ],
            )

            result = runner.invoke(main, ["--no-tokenizer", "--json"])

        assert result.exit_code == 2

    def test_exit_0_when_some_probes_succeed(self):
        """Exit code 0 when at least one probe succeeded."""

        runner = CliRunner()

        with patch("mcp_analysis.cli.get_all_adapters") as mock_adapters, \
             patch("mcp_analysis.cli.analyze_adapter") as mock_analyze:

            mock_adapter = AsyncMock()
            mock_adapter.name = "TestCLI"
            mock_adapter.slug = "testcli"
            mock_adapter.detect = AsyncMock(return_value=True)
            mock_adapter.get_config_path = lambda: "/test/path"
            mock_adapters.return_value = [mock_adapter]

            mock_analyze.return_value = _make_analysis()

            result = runner.invoke(main, ["--no-tokenizer", "--json"])

        assert result.exit_code == 0

    def test_exit_0_when_no_servers(self):
        """Exit code 0 when a CLI has zero servers (disabled)."""
        runner = CliRunner()

        with patch("mcp_analysis.cli.get_all_adapters") as mock_adapters, \
             patch("mcp_analysis.cli.analyze_adapter") as mock_analyze:

            mock_adapter = AsyncMock()
            mock_adapter.name = "TestCLI"
            mock_adapter.slug = "testcli"
            mock_adapter.detect = AsyncMock(return_value=True)
            mock_adapter.get_config_path = lambda: "/test/path"
            mock_adapters.return_value = [mock_adapter]

            mock_analyze.return_value = CliAnalysis(
                cli="TestCLI",
                slug="testcli",
                config_path="/test/path",
                servers=[],
                disabled_server_count=3,
            )

            result = runner.invoke(main, ["--no-tokenizer", "--json"])

        assert result.exit_code == 0

