# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `--dry-run` flag to preview discovered servers without probing them
- Exit code 2 when all server probes fail (distinct from exit code 1 = no configs found)
- Comprehensive test suite: 67 → 124 tests, 67% → 93% line coverage
- CI coverage gate (`--cov-fail-under=90`) and uv dependency caching
- New test files: `test_analyzer.py`, `test_cli.py`, `test_probe.py`, `test_registry.py`, `conftest.py`

### Fixed

- Remote HTTP probes now call `raise_for_status()` on both `initialize` and `tools/list` responses — auth/server errors are caught immediately instead of producing confusing downstream failures
- `httpx.AsyncClient` is now shared across retry attempts instead of creating a fresh connection pool per retry
- Markdown error rows now place values in the correct columns
- Dynamic adapter slug detection in `--all` logic — new adapters no longer require updating a hardcoded flag check in `cli.py`

### Changed

- Context budget model list updated: now shows MiniMax M2.7, Gemma 4, Qwen 3.5, Opus 4.7, Gemini 3.1 Pro

## [0.1.0] — 2026-04-22

### Added

- Initial release
- Auto-detection of MCP configurations for OpenCode, Gemini CLI, Claude Code, and Codex CLI
- Exact token counting via `tiktoken` (cl100k_base) with chars/4 fallback
- Local server probing via MCP SDK stdio transport
- Remote server probing via HTTP JSON-RPC (with SSE response support)
- Rich terminal table output with context budget visualization (MiniMax M2.7, Gemma 4, Qwen 3.5, Opus 4.7, Gemini 3.1 Pro)
- JSON and Markdown output formats
- Environment variable resolution for `{env:VAR}`, `${VAR}`, and `$VAR` patterns
- `--skip-local` flag to avoid spawning local server processes
- `--no-tokenizer` flag for faster estimation-only mode
- Configurable per-server timeout via `--timeout`
- Resilient Codex TOML parsing (extracts MCP sections only, tolerates invalid TOML elsewhere)
- Content-based config detection to prevent false positives from empty/metadata-only files
