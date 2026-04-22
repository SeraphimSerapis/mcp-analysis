# mcp-analysis

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-%3E%3D3.11-brightgreen.svg)](https://python.org)

**Know exactly how much context your MCP tools cost — before you type a single prompt.**

Every MCP tool definition eats into your model's context window. If you're running
10 servers with 200+ tools, that can burn 50-100K tokens just on tool schemas.
`mcp-analysis` connects to each configured server, calls `tools/list`, and reports
exact token costs with a context budget breakdown.

## Quick Start

```bash
# Install from git with uv
uv tool install git+https://github.com/SeraphimSerapis/mcp-analysis

# Run it
mcp-analysis
```

Or run without installing:

```bash
uvx --from git+https://github.com/SeraphimSerapis/mcp-analysis mcp-analysis
```

## Supported CLIs

| CLI | Config Path | Format |
|-----|-------------|--------|
| [OpenCode](https://opencode.ai) | `~/.config/opencode/opencode.jsonc` | JSONC |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli) | `~/.gemini/settings.json` | JSON |
| [Claude Code](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code) | `~/.claude.json` | JSON |
| [Codex CLI](https://developers.openai.com/codex/mcp) | `~/.codex/config.toml` | TOML |

> **Don't see your CLI?** Adapters are easy to add — see [Contributing](#contributing).

## Usage

```bash
# Auto-detect all installed CLIs (default)
mcp-analysis

# Analyze specific CLIs only
mcp-analysis --opencode
mcp-analysis --gemini

# Skip local servers (no subprocess spawning)
mcp-analysis --skip-local

# Machine-readable output
mcp-analysis --json
mcp-analysis --markdown

# Disable exact tokenizer (faster, uses chars/4 estimate)
mcp-analysis --no-tokenizer

# Custom timeout per server (seconds)
mcp-analysis --timeout 30
```

## Example Output

```
━━━ Gemini CLI ━━━ (~/.gemini/settings.json)

 Server                      Tools  Tokens (exact)       Chars
 ☁ homeassistant                80          44,410     175,106
 ☁ grafana                      50          15,656      61,958
 ☁ firecrawl                    12           8,281      31,561
 ☁ playwright                   21           3,929      15,778
  TOTAL                        163         72,276

Context budget reference:
  MiniMax M2.7 (192K)    ███████░░░░░░░░░░░░░ 36.8%
  Gemma 4 (256K)         ██████░░░░░░░░░░░░░░ 27.6%
  Qwen 3.5 (256K)        ██████░░░░░░░░░░░░░░ 27.6%
  Opus 4.7 (1M)          █░░░░░░░░░░░░░░░░░░░ 6.9%
  Gemini 3.1 Pro (1M)    █░░░░░░░░░░░░░░░░░░░ 6.9%
```

## Development

```bash
# Clone
git clone https://github.com/SeraphimSerapis/mcp-analysis.git
cd mcp-analysis

# Install with dev dependencies
uv sync

# Run locally
uv run mcp-analysis

# Run tests
uv run pytest -v

# Run tests with coverage
uv run pytest --cov=mcp_analysis
```

## Project Structure

```
src/mcp_analysis/
  cli.py            Click CLI entry point
  types.py          Dataclass definitions
  analyzer.py       Orchestrator: parse → probe → aggregate
  probe.py          MCP client (stdio via SDK + HTTP via httpx)
  tokenizer.py      Token counting (tiktoken cl100k_base or chars/4)
  env.py            Environment variable resolution
  output.py         Formatters (rich table, JSON, Markdown)
  adapters/
    base.py         ConfigAdapter ABC
    registry.py     Adapter list — register new CLIs here
    opencode.py     OpenCode (JSONC)
    gemini.py       Gemini CLI (JSON)
    claude.py       Claude Code (JSON)
    codex.py        Codex CLI (TOML)
tests/
  fixtures/         Config file fixtures for testing
  test_helpers.py   JSONC/SSE parser tests
  test_adapters.py  Adapter detection + parsing tests
  test_env.py       Env var resolution tests
  test_tokenizer.py Tokenizer tests
  test_output.py    Output formatter tests
```

## Security

This tool reads your existing MCP config files and connects to the servers
**you already configured**. It does not send telemetry, modify configs, or call
any MCP tools — it only lists them. See [SECURITY.md](SECURITY.md) for the full
trust model and vulnerability reporting instructions.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on adding new CLI adapters
and the development workflow.

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).

## License

[Apache License 2.0](LICENSE)
