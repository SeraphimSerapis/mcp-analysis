"""Adapter registration — add new CLIs here."""

from __future__ import annotations

from .base import ConfigAdapter
from .claude import ClaudeAdapter
from .codex import CodexAdapter
from .gemini import GeminiAdapter
from .opencode import OpenCodeAdapter


def get_all_adapters() -> list[ConfigAdapter]:
    return [
        OpenCodeAdapter(),
        GeminiAdapter(),
        ClaudeAdapter(),
        CodexAdapter(),
    ]
