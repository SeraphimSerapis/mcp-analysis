"""Base adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from mcp_analysis.types import McpServerConfig


class ConfigAdapter(ABC):
    """To add support for a new CLI, subclass this and register in registry.py."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name, e.g. 'OpenCode'."""

    @property
    @abstractmethod
    def slug(self) -> str:
        """CLI flag slug, e.g. 'opencode'."""

    @abstractmethod
    def get_config_path(self) -> str:
        """Return the config file path that was used (for display)."""

    @abstractmethod
    async def detect(self) -> bool:
        """Detect whether this CLI is configured on the current machine."""

    @abstractmethod
    async def parse(self) -> list[McpServerConfig]:
        """Parse config and return normalized MCP server definitions."""
