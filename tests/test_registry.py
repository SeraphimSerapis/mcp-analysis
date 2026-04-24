"""Tests for adapter registry."""

from mcp_analysis.adapters.base import ConfigAdapter
from mcp_analysis.adapters.registry import get_all_adapters


class TestAdapterRegistry:
    def test_returns_list(self):
        adapters = get_all_adapters()
        assert isinstance(adapters, list)
        assert len(adapters) >= 4  # opencode, gemini, claude, codex

    def test_all_are_config_adapters(self):
        adapters = get_all_adapters()
        for adapter in adapters:
            assert isinstance(adapter, ConfigAdapter)

    def test_unique_slugs(self):
        adapters = get_all_adapters()
        slugs = [a.slug for a in adapters]
        assert len(slugs) == len(set(slugs)), f"Duplicate slugs: {slugs}"

    def test_unique_names(self):
        adapters = get_all_adapters()
        names = [a.name for a in adapters]
        assert len(names) == len(set(names)), f"Duplicate names: {names}"

    def test_expected_adapters_present(self):
        adapters = get_all_adapters()
        slugs = {a.slug for a in adapters}
        assert "opencode" in slugs
        assert "gemini" in slugs
        assert "claude" in slugs
        assert "codex" in slugs
