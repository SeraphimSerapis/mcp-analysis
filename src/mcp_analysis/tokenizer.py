"""Token counting module.

Provides two strategies:
  1. Rough estimate: chars / 4  (always available, fast)
  2. Exact count:    tiktoken cl100k_base  (optional, accurate)
"""

from __future__ import annotations

from dataclasses import dataclass

_encoder = None
_ready = False


@dataclass
class TokenCount:
    estimated: int
    exact: int | None


def init_tokenizer() -> bool:
    """Initialize the tiktoken tokenizer. Call once at startup."""
    global _encoder, _ready
    try:
        import tiktoken

        _encoder = tiktoken.get_encoding("cl100k_base")
        _ready = True
        return True
    except Exception:
        _ready = False
        return False


def count_tokens(text: str) -> TokenCount:
    """Count tokens for a string."""
    estimated = -(-len(text) // 4)  # ceil division
    exact = None
    if _ready:
        assert _encoder is not None  # set in init_tokenizer() when _ready is True
        exact = len(_encoder.encode(text))
    return TokenCount(estimated=estimated, exact=exact)


def has_exact_tokenizer() -> bool:
    """Whether the real tokenizer is available."""
    return _ready
