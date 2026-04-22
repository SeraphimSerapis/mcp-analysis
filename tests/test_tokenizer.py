"""Tests for tokenizer module."""

from mcp_analysis.tokenizer import init_tokenizer, count_tokens, has_exact_tokenizer


class TestTokenizer:
    def test_estimated_count(self):
        result = count_tokens("abcdefghijklmnop")  # 16 chars
        assert result.estimated == 4  # ceil(16 / 4)

    def test_ceil_rounding(self):
        result = count_tokens("a" * 10)
        assert result.estimated == 3  # ceil(10 / 4)

    def test_empty_string(self):
        result = count_tokens("")
        assert result.estimated == 0

    def test_init_and_exact(self):
        ok = init_tokenizer()
        assert ok is True
        assert has_exact_tokenizer() is True

        result = count_tokens("Hello, world!")
        assert result.exact is not None
        assert result.exact > 0

    def test_exact_differs_from_estimate(self):
        init_tokenizer()
        import json
        content = json.dumps({
            "name": "test_tool",
            "description": "A test tool",
            "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
        })
        result = count_tokens(content)
        assert result.exact is not None
        assert result.exact != result.estimated
