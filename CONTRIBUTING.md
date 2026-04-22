# Contributing to mcp-analysis

Thank you for your interest in contributing! This guide covers the most common
contribution: **adding support for a new coding CLI**.

## Project Structure

```
src/mcp_analysis/
  cli.py            Click CLI entry point
  types.py          Dataclass definitions
  analyzer.py       Orchestrator: parse → probe → aggregate
  probe.py          MCP client (stdio via SDK + HTTP via httpx)
  tokenizer.py      Token counting (tiktoken or chars/4)
  env.py            Environment variable resolution
  output.py         Formatters (rich table, JSON, Markdown)
  adapters/
    base.py         ConfigAdapter ABC — implement this for new CLIs
    registry.py     Adapter list — register new adapters here
    opencode.py     OpenCode (JSONC)
    gemini.py       Gemini CLI (JSON)
    claude.py       Claude Code (JSON)
    codex.py        Codex CLI (TOML)
```

## Adding Support for a New CLI

### Step 1: Create the adapter

Create `src/mcp_analysis/adapters/yourcli.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from .base import ConfigAdapter
from mcp_analysis.types import McpServerConfig

_DEFAULT_PATH = Path.home() / ".yourcli" / "config.json"


class YourCliAdapter(ConfigAdapter):
    def __init__(self, config_path: str | Path | None = None):
        self._path = Path(config_path) if config_path else _DEFAULT_PATH

    @property
    def name(self) -> str:
        return "Your CLI"

    @property
    def slug(self) -> str:
        return "yourcli"

    def get_config_path(self) -> str:
        return str(self._path)

    async def detect(self) -> bool:
        try:
            config = json.loads(self._path.read_text())
            return bool(config.get("mcpServers") and len(config["mcpServers"]) > 0)
        except Exception:
            return False

    async def parse(self) -> list[McpServerConfig]:
        config = json.loads(self._path.read_text())
        servers: list[McpServerConfig] = []

        for name, defn in config.get("mcpServers", {}).items():
            servers.append(McpServerConfig(
                name=name,
                type="remote" if defn.get("url") else "local",
                command=[defn["command"], *defn.get("args", [])] if defn.get("command") else None,
                url=defn.get("url"),
                headers=defn.get("headers"),
                environment=defn.get("env"),
                enabled=defn.get("disabled") is not True,
            ))

        return servers
```

### Step 2: Register it

In `src/mcp_analysis/adapters/registry.py`:

```python
from .yourcli import YourCliAdapter

def get_all_adapters() -> list[ConfigAdapter]:
    return [
        ...
        YourCliAdapter(),   # ← add here
    ]
```

### Step 3: Add the CLI flag

In `src/mcp_analysis/cli.py`:

1. Add `@click.option("--yourcli", is_flag=True, help="Analyze Your CLI config")`
2. Add `yourcli` parameter to the `main()` function
3. Pass it to the `CliOptions` constructor

In `src/mcp_analysis/types.py`, add `yourcli: bool = False` to `CliOptions`.

### Step 4: Add tests

Create a fixture in `tests/fixtures/yourcli.json` and add tests in
`tests/test_adapters.py` following the existing patterns.

### Step 5: Build and test

```bash
uv run mcp-analysis --yourcli
uv run pytest -v
```

## Development Workflow

### Setup

```bash
uv sync          # Install all dependencies
```

### Testing

```bash
uv run pytest -v            # Run all tests
uv run pytest -v -k "test_detect"  # Run specific tests
```

### Manual Testing

```bash
# Test against a specific CLI config
uv run mcp-analysis --opencode
uv run mcp-analysis --gemini

# Skip spawning local servers (faster iteration)
uv run mcp-analysis --skip-local

# Machine-readable output
uv run mcp-analysis --json
```

## Submitting Changes

1. **Fork** the repo and create a feature branch from `main`.
2. **Make your changes** — keep commits focused and atomic.
3. **Run `uv run pytest`** to make sure all tests pass.
4. **Open a PR** with a clear description of what you changed and why.

### PR Guidelines

- One adapter per PR (keep changes reviewable).
- Include test fixtures and tests for new adapters.
- Follow the existing code style (type hints, docstrings).
- Update `README.md` supported CLIs table if adding a new adapter.
