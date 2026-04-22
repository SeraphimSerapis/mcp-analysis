"""Core analyzer — orchestrates adapter → probe → aggregate."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from rich.console import Console

from .adapters.base import ConfigAdapter
from .probe import probe_server
from .tokenizer import has_exact_tokenizer
from .types import CliAnalysis, CliOptions, FullReport

stderr = Console(stderr=True)


async def analyze_adapter(adapter: ConfigAdapter, options: CliOptions) -> CliAnalysis:
    """Analyze all enabled servers for a single CLI adapter."""
    servers = await adapter.parse()
    enabled = [s for s in servers if s.enabled]
    disabled_count = len(servers) - len(enabled)

    results = []
    for server in enabled:
        if options.skip_local and server.type == "local":
            continue

        icon = "[blue]☁[/]" if server.type == "remote" else "[green]⚙[/]"
        stderr.print(f"  {icon} Probing {server.name}...", end="")

        result = await probe_server(server, options.timeout)

        if result.error:
            stderr.print(f" [red]✗ {result.error[:50]}[/]")
        else:
            tokens = result.exact_tokens if has_exact_tokenizer() else result.estimated_tokens
            stderr.print(f" [green]✓ {len(result.tools)} tools, ~{tokens:,} tokens[/]")

        results.append(result)

    if disabled_count > 0 and not enabled:
        stderr.print(f"  [dim]{disabled_count} server(s) configured but all disabled[/]")
    elif disabled_count > 0:
        stderr.print(f"  [dim]({disabled_count} additional server(s) disabled)[/]")

    total_tools = sum(len(r.tools) for r in results)
    total_estimated = sum(r.estimated_tokens for r in results)
    total_exact = (
        sum(r.exact_tokens or 0 for r in results) if has_exact_tokenizer() else None
    )

    return CliAnalysis(
        cli=adapter.name,
        slug=adapter.slug,
        config_path=adapter.get_config_path(),
        servers=results,
        total_tools=total_tools,
        total_estimated_tokens=total_estimated,
        total_exact_tokens=total_exact,
        disabled_server_count=disabled_count,
    )


def build_report(analyses: list[CliAnalysis]) -> FullReport:
    """Aggregate CLI analyses into a full report."""
    total_tools = sum(a.total_tools for a in analyses)
    total_estimated = sum(a.total_estimated_tokens for a in analyses)

    has_exact = any(a.total_exact_tokens is not None for a in analyses)
    total_exact = sum(a.total_exact_tokens or 0 for a in analyses) if has_exact else None

    return FullReport(
        analyses=analyses,
        total_tools=total_tools,
        total_estimated_tokens=total_estimated,
        total_exact_tokens=total_exact,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
