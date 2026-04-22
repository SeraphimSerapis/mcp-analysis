"""Tests for environment variable resolution."""

import os

import pytest

from mcp_analysis.env import resolve_env_vars, resolve_headers, resolve_environment


class TestResolveEnvVars:
    def test_opencode_pattern(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "hello")
        assert resolve_env_vars("{env:TEST_VAR}") == "hello"

    def test_shell_braced_pattern(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "hello")
        assert resolve_env_vars("${TEST_VAR}") == "hello"

    def test_bare_dollar_pattern(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "hello")
        assert resolve_env_vars("$TEST_VAR") == "hello"

    def test_mixed_patterns(self, monkeypatch):
        monkeypatch.setenv("MY_TOKEN", "secret123")
        assert resolve_env_vars("Bearer {env:MY_TOKEN}") == "Bearer secret123"

    def test_embedded_braced(self, monkeypatch):
        monkeypatch.setenv("MY_TOKEN", "secret123")
        assert resolve_env_vars("token=${MY_TOKEN}&foo") == "token=secret123&foo"

    def test_missing_vars_resolve_to_empty(self):
        assert resolve_env_vars("{env:NONEXISTENT}") == ""
        assert resolve_env_vars("${NONEXISTENT}") == ""
        assert resolve_env_vars("$NONEXISTENT") == ""

    def test_plain_string_unchanged(self):
        assert resolve_env_vars("no-vars-here") == "no-vars-here"

    def test_empty_string(self):
        assert resolve_env_vars("") == ""


class TestResolveHeaders:
    def test_resolves_env_vars(self, monkeypatch):
        monkeypatch.setenv("AUTH_TOKEN", "bearer-xyz")
        result = resolve_headers({
            "Authorization": "Bearer {env:AUTH_TOKEN}",
            "X-Static": "plain-value",
        })
        assert result == {
            "Authorization": "Bearer bearer-xyz",
            "X-Static": "plain-value",
        }

    def test_none_returns_empty(self):
        assert resolve_headers(None) == {}


class TestResolveEnvironment:
    def test_resolves_env_vars(self, monkeypatch):
        monkeypatch.setenv("DB_HOST", "localhost")
        result = resolve_environment({"DATABASE_URL": "${DB_HOST}:5432", "STATIC": "value"})
        assert result == {"DATABASE_URL": "localhost:5432", "STATIC": "value"}

    def test_none_returns_empty(self):
        assert resolve_environment(None) == {}
