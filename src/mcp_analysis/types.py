"""Core type definitions for mcp-analysis."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class McpServerConfig:
    """Normalized MCP server configuration (adapter output)."""

    name: str
    type: str  # "local" or "remote"
    command: list[str] | None = None
    url: str | None = None
    headers: dict[str, str] | None = None
    environment: dict[str, str] | None = None
    enabled: bool = True


@dataclass
class ToolAnalysis:
    """Single tool from a server's tools/list response."""

    name: str
    description: str
    char_count: int
    raw_json: str


@dataclass
class ServerResult:
    """Result of probing one MCP server."""

    name: str
    type: str
    tools: list[ToolAnalysis] = field(default_factory=list)
    total_chars: int = 0
    estimated_tokens: int = 0
    exact_tokens: int | None = None
    error: str | None = None


@dataclass
class CliAnalysis:
    """Full analysis for one CLI."""

    cli: str
    slug: str
    config_path: str
    servers: list[ServerResult] = field(default_factory=list)
    total_tools: int = 0
    total_estimated_tokens: int = 0
    total_exact_tokens: int | None = None
    disabled_server_count: int = 0


@dataclass
class FullReport:
    """Aggregated result across all CLIs."""

    analyses: list[CliAnalysis] = field(default_factory=list)
    total_tools: int = 0
    total_estimated_tokens: int = 0
    total_exact_tokens: int | None = None
    timestamp: str = ""


@dataclass
class CliOptions:
    """CLI options parsed from command-line arguments."""

    all: bool = True
    opencode: bool = False
    gemini: bool = False
    claude: bool = False
    codex: bool = False
    json_output: bool = False
    markdown: bool = False
    skip_local: bool = False
    timeout: float = 15.0
    no_tokenizer: bool = False
