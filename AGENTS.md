# AGENTS.md — mcp-analysis

Analyze MCP (Model Context Protocol) tool token consumption across coding AI CLIs.
Every MCP tool definition eats into a model's context window before the user types a single prompt.
This tool connects to each configured server, calls `tools/list`, and reports exact token costs.

## Architecture

```
src/mcp_analysis/
  cli.py            Click CLI entry point, wires adapters → analyzer → output
  │
  ├── adapters/
  │   ├── base.py       ConfigAdapter ABC (all adapters implement this)
  │   ├── registry.py   Adapter registration (add new CLIs here)
  │   ├── opencode.py   OpenCode   — JSONC at ~/.config/opencode/opencode.jsonc
  │   ├── gemini.py     Gemini CLI — JSON  at ~/.gemini/settings.json
  │   ├── claude.py     Claude Code — JSON at ~/.claude.json or ~/.claude/settings.json
  │   └── codex.py      Codex CLI  — TOML  at ~/.codex/config.toml
  │
  ├── analyzer.py   Orchestrates: adapter.parse() → probe each server → aggregate
  ├── probe.py      MCP client: stdio transport (MCP SDK) or HTTP (httpx)
  ├── tokenizer.py  Token counting: exact (tiktoken cl100k_base) or estimated (chars/4)
  ├── env.py        Resolves env var patterns: {env:VAR}, ${VAR}, $VAR
  ├── output.py     Formatters: rich terminal table, JSON, Markdown
  └── types.py      All shared dataclass definitions
```

## Data Flow

```
ConfigAdapter.parse()          → list[McpServerConfig]  (normalized server list)
  ↓
analyzer.analyze_adapter()     → probe_server() per server (parallel, semaphore-limited)
  ↓
probe._probe_local()           → MCP SDK stdio_client → tools/list → list[ToolAnalysis]
probe._probe_remote()          → httpx JSON-RPC        → tools/list → list[ToolAnalysis]
  ↓
output.format_table/json/md()  → FullReport → stdout
```

## Key Types (src/mcp_analysis/types.py)

- **`McpServerConfig`** — Normalized adapter output: `name`, `type` (local/remote), `command`, `url`, `headers`, `environment`, `enabled`
- **`ToolAnalysis`** — Single tool: `name`, `description`, `char_count`, `raw_json`
- **`ServerResult`** — Probe result per server: tools list, token counts, error
- **`CliAnalysis`** — Per-CLI aggregation: servers, totals, `disabled_server_count`
- **`FullReport`** — Cross-CLI aggregation for output formatters
- **`CliOptions`** — CLI flag values from click

## Adding a New CLI Adapter

### Step 1: Create the adapter file

Create `src/mcp_analysis/adapters/<yourcli>.py` implementing `ConfigAdapter`:

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
            # Only detect if the file actually contains MCP server config.
            # Config files may exist for non-MCP settings.
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
        OpenCodeAdapter(),
        GeminiAdapter(),
        ClaudeAdapter(),
        CodexAdapter(),
        YourCliAdapter(),   # ← add here
    ]
```

### Step 3: Add the CLI flag

In `src/mcp_analysis/cli.py`:

1. Add `@click.option("--yourcli", is_flag=True, help="Analyze Your CLI config")`
2. Add `yourcli` parameter to the `main()` function
3. Pass it to the `CliOptions` constructor

In `src/mcp_analysis/types.py`, add `yourcli: bool = False` to `CliOptions`.

### Step 4: Build and test

```bash
uv run mcp-analysis --yourcli
uv run pytest -v
```

## Adapter Patterns by Config Format

Each CLI has its own config format. Key differences to handle:

| CLI | Format | Config key | Server type detection | Enabled field |
|-----|--------|------------|----------------------|---------------|
| OpenCode | JSONC | `mcp.<name>` | `type: "remote"` / `"local"` | `enabled is not False` |
| Gemini CLI | JSON | `mcpServers.<name>` | `url` or `httpUrl` present → remote | `disabled is not True` |
| Claude Code | JSON | `mcpServers.<name>` | `url` present → remote | `disabled is not True` |
| Codex CLI | TOML | `[mcp_servers.<name>]` | `url` present → remote | `enabled is not False` |

### Remote server URL fields

Different CLIs use different keys for HTTP endpoints:

- **OpenCode**: `url` (with `type: "remote"`)
- **Gemini CLI**: `url` (SSE) **or** `httpUrl` (streamable HTTP) — check both
- **Claude Code**: `url`
- **Codex CLI**: `url`

### Header resolution

Headers may contain environment variable references. The `env.py` module resolves:
- `{env:VAR_NAME}` — OpenCode style
- `${VAR_NAME}` — Gemini/Claude shell style
- `$VAR_NAME` — bare shell style

Codex uses a different mechanism (`bearer_token_env_var`, `http_headers`, `env_http_headers`) which the adapter resolves directly from `os.environ`.

## Probing (src/mcp_analysis/probe.py)

- **Local (stdio)**: Uses the official MCP Python SDK (`stdio_client` + `ClientSession`). Calls `session.initialize()` then `session.list_tools()`, both wrapped in `asyncio.wait_for()` with configurable timeout.
- **Remote (HTTP)**: Two-step JSON-RPC over `httpx`: first `initialize`, then `tools/list`. Handles both plain JSON and SSE-wrapped responses. Captures `Mcp-Session` headers for session continuity. **Retries once** on transient `httpx.TransportError` / `TimeoutException` with 1s backoff.
- **SSE parsing**: When an SSE stream contains multiple `data:` events, the parser matches on JSON-RPC `id` field (not just the last event) to avoid returning the wrong response.
- **Parallelism**: `analyze_adapter()` probes all servers concurrently via `asyncio.gather()` with a semaphore (default max 5) to avoid spawning too many subprocesses.

Both paths use the configurable timeout (default 15s).

## Output (src/mcp_analysis/output.py)

Three formatters, all driven by `FullReport`:

- **Table** (default): Rich terminal table with progress bars showing context budget usage against MiniMax M2.7 (192K), Gemma 4 (256K), Qwen 3.5 (256K), Opus 4.7 (1M), and Gemini 3.1 Pro (1M).
- **JSON** (`--json`): Machine-readable full report via `dataclasses.asdict()`.
- **Markdown** (`--markdown`): GitHub-friendly table format.

The table distinguishes between "No MCP servers configured" (zero servers in config) and "N server(s) configured but disabled" (servers exist but all have `enabled: False`).

## Dependencies

- `mcp` — Official MCP Python SDK (stdio client transport)
- `httpx` — HTTP client for remote server probing
- `click` — CLI argument parsing
- `rich` — Terminal colors and tables
- `tiktoken` — Exact token counting (cl100k_base)
- `tomllib` — TOML parsing (stdlib, Python 3.11+)

## Conventions

- Python 3.11+ required (for `tomllib` stdlib).
- Source layout: `src/mcp_analysis/`.
- All adapters accept an optional config path for testability.
- `detect()` must validate config content, not just file existence.
- Status/progress output goes to `stderr` (via `rich.Console(stderr=True)`); formatted reports go to `stdout`.
- Preserve all existing comments and docstrings when editing.
- **Linting**: `ruff` (rules: E, F, W, I, UP, B, SIM). Run `uv run ruff check src/`.
- **Type checking**: `mypy` with `ignore_missing_imports` and `check_untyped_defs`. Run `uv run mypy src/mcp_analysis/`.
- CI runs lint → type check → tests (fail fast on trivial issues).
