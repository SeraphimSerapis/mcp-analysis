"""Environment-variable resolution utility.

Handles patterns:
  {env:VAR_NAME}  — OpenCode style
  ${VAR_NAME}     — Gemini/Claude shell style
  $VAR_NAME       — bare shell style
"""

from __future__ import annotations

import os
import re


def resolve_env_vars(value: str) -> str:
    """Resolve environment variable references in a string."""
    # OpenCode pattern: {env:VAR_NAME}
    resolved = re.sub(
        r"\{env:([^}]+)\}",
        lambda m: os.environ.get(m.group(1), ""),
        value,
    )
    # Shell-style pattern: ${VAR_NAME}
    resolved = re.sub(
        r"\$\{([^}]+)\}",
        lambda m: os.environ.get(m.group(1), ""),
        resolved,
    )
    # Bare shell-style pattern: $VAR_NAME (must run after ${VAR})
    resolved = re.sub(
        r"\$([A-Za-z_][A-Za-z0-9_]*)",
        lambda m: os.environ.get(m.group(1), ""),
        resolved,
    )
    return resolved


def resolve_headers(headers: dict[str, str] | None) -> dict[str, str]:
    """Resolve env vars in header values."""
    if not headers:
        return {}
    return {k: resolve_env_vars(v) for k, v in headers.items()}


def resolve_environment(env: dict[str, str] | None) -> dict[str, str]:
    """Resolve env vars in environment values."""
    if not env:
        return {}
    return {k: resolve_env_vars(v) for k, v in env.items()}
