"""Claude Code adapter.

Config locations (checked in order):
  1. ~/.claude.json           (global)
  2. ~/.claude/settings.json  (global alt)

Schema: { mcpServers: { "name": { command, args, env } } }
"""

from __future__ import annotations

import json
from pathlib import Path

from mcp_analysis.types import McpServerConfig

from .base import ConfigAdapter

_DEFAULT_CANDIDATES = [
    Path.home() / ".claude.json",
    Path.home() / ".claude" / "settings.json",
]


class ClaudeAdapter(ConfigAdapter):
    def __init__(self, candidates: list[str | Path] | None = None):
        self._candidates = [Path(c) for c in candidates] if candidates else _DEFAULT_CANDIDATES
        self._resolved_path: Path | None = None
        self._cached_config: dict | None = None

    @property
    def name(self) -> str:
        return "Claude Code"

    @property
    def slug(self) -> str:
        return "claude"

    def get_config_path(self) -> str:
        return str(self._resolved_path or "")

    async def detect(self) -> bool:
        for candidate in self._candidates:
            try:
                config = json.loads(candidate.read_text())
                # Only detect if the file actually contains MCP server config.
                # ~/.claude.json can exist as a metadata-only file.
                if config.get("mcpServers") and len(config["mcpServers"]) > 0:
                    self._resolved_path = candidate
                    self._cached_config = config
                    return True
            except Exception:
                continue
        return False

    async def parse(self) -> list[McpServerConfig]:
        config = self._cached_config
        if config is None:
            if not await self.detect():
                return []
            config = self._cached_config

        mcp_block = config.get("mcpServers", {})  # type: ignore[union-attr]
        servers: list[McpServerConfig] = []

        for srv_name, defn in mcp_block.items():
            command = (
                [defn["command"], *(defn.get("args", []))]
                if defn.get("command")
                else None
            )
            srv_type = "remote" if defn.get("url") else "local"

            servers.append(McpServerConfig(
                name=srv_name,
                type=srv_type,
                command=command,
                url=defn.get("url"),
                headers=defn.get("headers"),
                environment=defn.get("env"),
                enabled=defn.get("disabled") is not True,
            ))

        return servers
