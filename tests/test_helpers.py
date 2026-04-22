"""Tests for internal helper functions (JSONC stripping, JSON-RPC parsing)."""

import pytest

from mcp_analysis.adapters.opencode import _strip_json_comments
from mcp_analysis.probe import _parse_jsonrpc_response


class TestStripJsonComments:
    def test_single_line_comment(self):
        text = '{\n  "key": "value" // this is a comment\n}'
        result = _strip_json_comments(text)
        assert "//" not in result
        assert '"key": "value"' in result

    def test_multi_line_comment(self):
        text = '{\n  /* block comment */\n  "key": "value"\n}'
        result = _strip_json_comments(text)
        assert "/*" not in result
        assert '"key": "value"' in result

    def test_preserves_urls_in_strings(self):
        text = '{\n  "$schema": "https://example.com/schema.json",\n  "url": "https://api.example.com/v1"\n}'
        result = _strip_json_comments(text)
        assert "https://example.com/schema.json" in result
        assert "https://api.example.com/v1" in result

    def test_preserves_escaped_quotes(self):
        text = r'{"key": "value with \"escaped\" quotes"}'
        result = _strip_json_comments(text)
        assert "escaped" in result

    def test_comment_after_url_string(self):
        text = '{\n  "url": "https://example.com" // comment after URL\n}'
        result = _strip_json_comments(text)
        assert "https://example.com" in result
        assert "comment after URL" not in result

    def test_empty_input(self):
        assert _strip_json_comments("") == ""

    def test_no_comments(self):
        text = '{"a": 1, "b": "hello"}'
        assert _strip_json_comments(text) == text


class TestParseJsonrpcResponse:
    def test_plain_json(self):
        text = '{"jsonrpc": "2.0", "result": {"tools": [{"name": "t1"}]}, "id": 1}'
        result = _parse_jsonrpc_response(text)
        assert result["result"]["tools"][0]["name"] == "t1"

    def test_json_with_whitespace(self):
        text = '  \n  {"jsonrpc": "2.0", "result": {}, "id": 1}  \n  '
        result = _parse_jsonrpc_response(text)
        assert result["jsonrpc"] == "2.0"

    def test_sse_format(self):
        text = (
            "event: message\n"
            'data: {"jsonrpc": "2.0", "result": {"tools": [{"name": "sse_tool"}]}, "id": 2}\n'
            "\n"
        )
        result = _parse_jsonrpc_response(text)
        assert result["result"]["tools"][0]["name"] == "sse_tool"

    def test_sse_with_done(self):
        text = (
            'data: {"jsonrpc": "2.0", "result": {"tools": []}, "id": 1}\n'
            "data: [DONE]\n"
        )
        result = _parse_jsonrpc_response(text)
        assert result["result"]["tools"] == []

    def test_unparseable_raises(self):
        with pytest.raises(RuntimeError, match="Could not parse"):
            _parse_jsonrpc_response("event: ping\n\n")
