"""OpenCode adapter.

Config: ~/.config/opencode/opencode.jsonc (JSONC)
Schema: { mcp: { "name": { type, command, url, headers, environment, enabled } } }
"""

from __future__ import annotations

import json
from pathlib import Path

from .base import ConfigAdapter
from mcp_analysis.types import McpServerConfig

_DEFAULT_PATH = Path.home() / ".config" / "opencode" / "opencode.jsonc"


def _strip_json_comments(text: str) -> str:
    """Strip // and /* */ comments from JSONC text, respecting strings."""
    result: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        # Inside a string — copy until closing quote
        if text[i] == '"':
            j = i + 1
            while j < n:
                if text[j] == '\\':
                    j += 2  # skip escaped char
                elif text[j] == '"':
                    j += 1
                    break
                else:
                    j += 1
            result.append(text[i:j])
            i = j
        # Single-line comment
        elif text[i:i + 2] == '//':
            j = text.find('\n', i)
            i = j if j != -1 else n
        # Multi-line comment
        elif text[i:i + 2] == '/*':
            j = text.find('*/', i + 2)
            i = j + 2 if j != -1 else n
        else:
            result.append(text[i])
            i += 1
    return ''.join(result)


class OpenCodeAdapter(ConfigAdapter):
    def __init__(self, config_path: str | Path | None = None):
        self._path = Path(config_path) if config_path else _DEFAULT_PATH

    @property
    def name(self) -> str:
        return "OpenCode"

    @property
    def slug(self) -> str:
        return "opencode"

    def get_config_path(self) -> str:
        return str(self._path)

    async def detect(self) -> bool:
        try:
            raw = self._path.read_text()
            config = json.loads(_strip_json_comments(raw))
            return bool(config.get("mcp") and len(config["mcp"]) > 0)
        except Exception:
            return False

    async def parse(self) -> list[McpServerConfig]:
        raw = self._path.read_text()
        config = json.loads(_strip_json_comments(raw))
        mcp_block = config.get("mcp", {})
        servers: list[McpServerConfig] = []

        for srv_name, defn in mcp_block.items():
            srv_type = "remote" if defn.get("type") == "remote" else "local"
            command = defn.get("command") if srv_type == "local" else None

            servers.append(McpServerConfig(
                name=srv_name,
                type=srv_type,
                command=command,
                url=defn.get("url"),
                headers=defn.get("headers"),
                environment=defn.get("environment"),
                enabled=defn.get("enabled", True) is not False,
            ))

        return servers
