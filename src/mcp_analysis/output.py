"""Output formatters: table (terminal), JSON, and Markdown."""

from __future__ import annotations

import json

from rich.console import Console
from rich.table import Table

from .tokenizer import has_exact_tokenizer
from .types import FullReport, ServerResult

_BUDGETS = [
    ("MiniMax M2.7 (192K)", 196_608),
    ("Gemma 4 (256K)", 262_144),
    ("Qwen 3.5 (256K)", 262_144),
    ("Opus 4.7 (1M)", 1_048_576),
    ("Gemini 3.1 Pro (1M)", 1_048_576),
]


# ─── Terminal table ────────────────────────────────────────────────────


def format_table(report: FullReport) -> str:
    """Render a rich terminal table."""
    console = Console(width=100)
    exact = has_exact_tokenizer()

    with console.capture() as capture:
        for cli in report.analyses:
            console.print()
            console.print(f"[bold cyan]━━━ {cli.cli} ━━━[/] [dim]({cli.config_path})[/]")
            console.print()

            if not cli.servers:
                if cli.disabled_server_count > 0:
                    console.print(f"  [dim]{cli.disabled_server_count} server(s) configured but disabled.[/]")
                else:
                    console.print("  [dim]No MCP servers configured.[/]")
                continue

            # Build rich table
            table = Table(show_header=True, header_style="dim", box=None, padding=(0, 1))
            table.add_column("Server", min_width=25)
            table.add_column("Tools", justify="right", min_width=6)
            tok_header = "Tokens (exact)" if exact else "Tokens (est.)"
            table.add_column(tok_header, justify="right", min_width=14)
            table.add_column("Chars", justify="right", min_width=10)

            sorted_servers = _sorted_servers(cli.servers, exact)

            for server in sorted_servers:
                tokens = (server.exact_tokens if exact else server.estimated_tokens) or 0
                if server.error:
                    icon = "[red]✗[/]"
                    table.add_row(
                        f"{icon} {server.name}",
                        "",
                        f"[red]error: {server.error[:35]}[/]",
                        "",
                    )
                else:
                    icon = "[blue]☁[/]" if server.type == "remote" else "[green]⚙[/]"
                    table.add_row(
                        f"{icon} {server.name}",
                        str(len(server.tools)),
                        f"{tokens:,}",
                        f"{server.total_chars:,}",
                    )

            console.print(table)

            total_tokens = (cli.total_exact_tokens if exact else cli.total_estimated_tokens) or 0
            console.print(f"  [bold]{'TOTAL':<25} {cli.total_tools:>6} {total_tokens:>14,}[/]")

            # Context budget reference (per CLI)
            _print_budget(console, total_tokens)

        console.print()

    return capture.get()


def _print_budget(console: Console, token_val: int) -> None:
    """Print context budget reference bars for a token count."""
    if token_val == 0:
        return
    console.print()
    console.print("[dim]Context budget:[/]")
    for name, budget in _BUDGETS:
        pct = token_val / budget * 100
        ratio = min(token_val / budget, 1.0)
        filled = round(ratio * 20)
        empty = 20 - filled
        color = "red" if ratio > 0.5 else "yellow" if ratio > 0.3 else "green"
        bar = f"[{color}]{'█' * filled}[/][dim]{'░' * empty}[/]"
        console.print(f"  [dim]{name:<22}[/] {bar} [dim]{pct:.1f}%[/]")


# ─── JSON ──────────────────────────────────────────────────────────────

_REDACTED = "[REDACTED]"


def format_json(report: FullReport) -> str:
    """Render as JSON.

    Header values are redacted to prevent accidental leakage of bearer
    tokens and other secrets in the serialized output.
    """
    import dataclasses

    raw = dataclasses.asdict(report)
    _redact_headers(raw)
    return json.dumps(raw, indent=2)


def _redact_headers(obj: dict | list) -> None:  # type: ignore[type-arg]
    """Recursively redact all ``headers`` values in a nested dict/list."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "headers" and isinstance(value, dict):
                for hk in value:
                    value[hk] = _REDACTED
            elif isinstance(value, (dict, list)):
                _redact_headers(value)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                _redact_headers(item)


# ─── Markdown ──────────────────────────────────────────────────────────


def format_markdown(report: FullReport) -> str:
    """Render as GitHub-friendly Markdown."""
    exact = has_exact_tokenizer()
    lines: list[str] = []

    lines.append("# MCP Tool Token Analysis")
    lines.append("")
    lines.append(f"> Generated: {report.timestamp}")
    lines.append("")

    for cli in report.analyses:
        lines.append(f"## {cli.cli}")
        lines.append("")
        lines.append(f"Config: `{cli.config_path}`")
        lines.append("")

        if not cli.servers:
            if cli.disabled_server_count > 0:
                lines.append(f"_{cli.disabled_server_count} server(s) configured but disabled._")
            else:
                lines.append("_No MCP servers configured._")
            lines.append("")
            continue

        tok_header = "Tokens (exact)" if exact else "Tokens (est.)"
        lines.append(f"| Server | Type | Tools | {tok_header} | Chars |")
        lines.append("|---|---|---:|---:|---:|")

        sorted_servers = _sorted_servers(cli.servers, exact)

        for server in sorted_servers:
            tokens = (server.exact_tokens if exact else server.estimated_tokens) or 0
            if server.error:
                lines.append(f"| {server.name} | {server.type} | — | ⚠ error | {server.error[:40]} |")
            else:
                lines.append(
                    f"| **{server.name}** | {server.type} | {len(server.tools)} | {tokens:,} | {server.total_chars:,} |"
                )

        total_tokens = (cli.total_exact_tokens if exact else cli.total_estimated_tokens) or 0
        lines.append(f"| **TOTAL** | | **{cli.total_tools}** | **{total_tokens:,}** | |")
        lines.append("")

    return "\n".join(lines)


# ─── Helpers ───────────────────────────────────────────────────────────


def _sorted_servers(servers: list[ServerResult], use_exact: bool) -> list[ServerResult]:
    """Sort servers by token count (descending)."""
    return sorted(
        servers,
        key=lambda s: (s.exact_tokens if use_exact else s.estimated_tokens) or 0,
        reverse=True,
    )
