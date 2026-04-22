"""OpenAI Codex adapter.

Config: ~/.codex/config.toml
Schema (TOML):
  [mcp_servers.<name>]
  command = "npx"
  args = ["-y", "@upstash/context7-mcp"]
  env = { MY_VAR = "value" }
  url = "https://mcp.example.com/mcp"
  bearer_token_env_var = "MY_TOKEN"
  http_headers = { "X-Region" = "us-east-1" }
  env_http_headers = { "Authorization" = "MY_AUTH_VAR" }
  enabled = true
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from mcp_analysis.types import McpServerConfig

from .base import ConfigAdapter

_DEFAULT_PATH = Path.home() / ".codex" / "config.toml"


class CodexAdapter(ConfigAdapter):
    def __init__(self, config_path: str | Path | None = None):
        self._path = Path(config_path) if config_path else _DEFAULT_PATH

    @property
    def name(self) -> str:
        return "Codex CLI"

    @property
    def slug(self) -> str:
        return "codex"

    def get_config_path(self) -> str:
        return str(self._path)

    async def detect(self) -> bool:
        try:
            raw = self._path.read_text()
            # Use the same section-extraction logic as parse() to tolerate
            # invalid TOML in non-MCP sections of the config file.
            has_mcp = any(
                line.strip().startswith("[mcp_servers")
                for line in raw.splitlines()
            )
            return has_mcp
        except Exception:
            return False

    async def parse(self) -> list[McpServerConfig]:
        raw = self._path.read_text()

        # Extract only the [mcp_servers.*] sections.
        # Codex config may contain invalid TOML in non-MCP sections
        # (e.g. bare keys without values), so we parse only what we need.
        mcp_lines: list[str] = []
        in_mcp = False
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("[mcp_servers"):
                in_mcp = True
            elif stripped.startswith("[") and not stripped.startswith("[mcp_servers"):
                in_mcp = False
            if in_mcp:
                mcp_lines.append(line)

        if not mcp_lines:
            return []

        config = tomllib.loads("\n".join(mcp_lines))
        mcp_block: dict = config.get("mcp_servers", {})
        servers: list[McpServerConfig] = []

        for srv_name, defn in mcp_block.items():
            is_remote = bool(defn.get("url"))
            srv_type = "remote" if is_remote else "local"

            # Build command array for stdio servers
            command: list[str] | None = None
            if not is_remote and defn.get("command"):
                command = [defn["command"], *(defn.get("args", []))]

            # Merge HTTP headers from static and env-resolved sources
            headers: dict[str, str] | None = None
            if is_remote:
                headers = {}

                # bearer_token_env_var → Authorization header
                bearer_var = defn.get("bearer_token_env_var")
                if bearer_var:
                    token = os.environ.get(bearer_var)
                    if token:
                        headers["Authorization"] = f"Bearer {token}"

                # Static headers
                if defn.get("http_headers"):
                    headers.update(defn["http_headers"])

                # Env-resolved headers
                if defn.get("env_http_headers"):
                    for header_name, env_var in defn["env_http_headers"].items():
                        val = os.environ.get(env_var)
                        if val:
                            headers[header_name] = val

                if not headers:
                    headers = None

            servers.append(McpServerConfig(
                name=srv_name,
                type=srv_type,
                command=command,
                url=defn.get("url"),
                headers=headers,
                environment=defn.get("env"),
                enabled=defn.get("enabled", True) is not False,
            ))

        return servers
