"""Gemini CLI adapter.

Config: ~/.gemini/settings.json
Schema: { mcpServers: { "name": { command, args, env, url, httpUrl, headers } } }

Gemini CLI supports three MCP transports:
  - stdio:            command + args
  - SSE:              url
  - Streamable HTTP:  httpUrl
"""

from __future__ import annotations

import json
from pathlib import Path

from .base import ConfigAdapter
from mcp_analysis.types import McpServerConfig

_DEFAULT_PATH = Path.home() / ".gemini" / "settings.json"


class GeminiAdapter(ConfigAdapter):
    def __init__(self, config_path: str | Path | None = None):
        self._path = Path(config_path) if config_path else _DEFAULT_PATH

    @property
    def name(self) -> str:
        return "Gemini CLI"

    @property
    def slug(self) -> str:
        return "gemini"

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
        mcp_block = config.get("mcpServers", {})
        servers: list[McpServerConfig] = []

        for srv_name, defn in mcp_block.items():
            command = (
                [defn["command"], *(defn.get("args", []))]
                if defn.get("command")
                else None
            )
            # Gemini CLI supports SSE (url) and streamable HTTP (httpUrl)
            remote_url = defn.get("url") or defn.get("httpUrl")
            srv_type = "remote" if remote_url else "local"

            servers.append(McpServerConfig(
                name=srv_name,
                type=srv_type,
                command=command,
                url=remote_url,
                headers=defn.get("headers"),
                environment=defn.get("env"),
                enabled=defn.get("disabled") is not True,
            ))

        return servers
