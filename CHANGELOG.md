# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-04-22

### Added

- Initial release
- Auto-detection of MCP configurations for OpenCode, Gemini CLI, Claude Code, and Codex CLI
- Exact token counting via `tiktoken` (cl100k_base) with chars/4 fallback
- Local server probing via MCP SDK stdio transport
- Remote server probing via HTTP JSON-RPC (with SSE response support)
- Rich terminal table output with context budget visualization (GPT-4o, Claude, Gemini 2.5 Pro, Qwen 3.5)
- JSON and Markdown output formats
- Environment variable resolution for `{env:VAR}`, `${VAR}`, and `$VAR` patterns
- `--skip-local` flag to avoid spawning local server processes
- `--no-tokenizer` flag for faster estimation-only mode
- Configurable per-server timeout via `--timeout`
- Resilient Codex TOML parsing (extracts MCP sections only, tolerates invalid TOML elsewhere)
- Content-based config detection to prevent false positives from empty/metadata-only files
