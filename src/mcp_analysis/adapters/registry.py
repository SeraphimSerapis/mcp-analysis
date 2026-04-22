"""Adapter registration — add new CLIs here."""

from __future__ import annotations

from .base import ConfigAdapter
from .opencode import OpenCodeAdapter
from .gemini import GeminiAdapter
from .claude import ClaudeAdapter
from .codex import CodexAdapter


def get_all_adapters() -> list[ConfigAdapter]:
    return [
        OpenCodeAdapter(),
        GeminiAdapter(),
        ClaudeAdapter(),
        CodexAdapter(),
    ]
