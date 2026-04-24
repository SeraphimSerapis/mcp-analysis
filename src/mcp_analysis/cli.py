"""CLI entry point for mcp-analysis."""

from __future__ import annotations

import asyncio
import sys

import click
from rich.console import Console

from .adapters.registry import get_all_adapters
from .analyzer import analyze_adapter, build_report
from .output import format_json, format_markdown, format_table
from .tokenizer import init_tokenizer
from .types import CliOptions

stderr = Console(stderr=True)


@click.command()
@click.option("--all", "analyze_all", is_flag=True, default=True, show_default=True, help="Auto-detect and analyze all installed CLIs")
@click.option("--opencode", is_flag=True, help="Analyze OpenCode config")
@click.option("--gemini", is_flag=True, help="Analyze Gemini CLI config")
@click.option("--claude", is_flag=True, help="Analyze Claude Code config")
@click.option("--codex", is_flag=True, help="Analyze Codex CLI config")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--markdown", is_flag=True, help="Output as Markdown")
@click.option("--skip-local", is_flag=True, help="Skip local servers (no subprocess spawning)")
@click.option("--timeout", default=15.0, show_default=True, help="Timeout per server in seconds")
@click.option("--no-tokenizer", is_flag=True, help="Disable exact tokenizer, use chars/4 estimate")
@click.option("--dry-run", is_flag=True, help="Show discovered servers without probing them")
@click.version_option(package_name="mcp-analysis")
def main(
    analyze_all: bool,
    opencode: bool,
    gemini: bool,
    claude: bool,
    codex: bool,
    json_output: bool,
    markdown: bool,
    skip_local: bool,
    timeout: float,
    no_tokenizer: bool,
    dry_run: bool,
) -> None:
    """Analyze MCP tool token consumption across coding AI CLIs."""
    options = CliOptions(
        all=analyze_all,
        opencode=opencode,
        gemini=gemini,
        claude=claude,
        codex=codex,
        json_output=json_output,
        markdown=markdown,
        skip_local=skip_local,
        timeout=timeout,
        no_tokenizer=no_tokenizer,
        dry_run=dry_run,
    )

    # If any specific CLI flag was set, disable --all.
    # Check dynamically against all registered adapter slugs so that
    # new adapters don't require updating this condition.
    all_adapters = get_all_adapters()
    if any(getattr(options, a.slug, False) for a in all_adapters):
        options.all = False

    asyncio.run(_run(options))


async def _run(options: CliOptions) -> None:
    # Initialize tokenizer (skip in dry-run mode)
    if options.dry_run:
        pass
    elif not options.no_tokenizer:
        stderr.print("[dim]Loading tokenizer...[/]", end="")
        ok = init_tokenizer()
        if ok:
            stderr.print(" [green]✓ cl100k_base[/]")
        else:
            stderr.print(" [yellow]⚠ falling back to chars/4 estimate[/]")
    else:
        stderr.print("[dim]Tokenizer disabled, using chars/4 estimate[/]")

    # Discover adapters
    all_adapters = get_all_adapters()
    adapters_to_run = []

    for adapter in all_adapters:
        requested = options.all or getattr(options, adapter.slug, False)
        if not requested:
            continue

        detected = await adapter.detect()
        if detected:
            adapters_to_run.append(adapter)
        elif not options.all:
            stderr.print(f"[yellow]⚠ {adapter.name} config not found at {adapter.get_config_path()}[/]")

    if not adapters_to_run:
        stderr.print("[red]No CLI configurations found.[/]")
        sys.exit(1)

    names = ", ".join(a.name for a in adapters_to_run)
    stderr.print(f"\n[dim]Found {len(adapters_to_run)} CLI(s): {names}[/]\n")

    # Dry-run mode: show discovered servers without probing
    if options.dry_run:
        for adapter in adapters_to_run:
            stderr.print(f"[bold]{adapter.name}[/] [dim]({adapter.get_config_path()})[/]")
            servers = await adapter.parse()
            enabled = [s for s in servers if s.enabled]
            disabled = len(servers) - len(enabled)

            for server in enabled:
                icon = "[blue]☁[/]" if server.type == "remote" else "[green]⚙[/]"
                detail = server.url or " ".join(server.command or [])
                skip_marker = " [dim](skip-local)[/]" if options.skip_local and server.type == "local" else ""
                stderr.print(f"  {icon} {server.name} [dim]→ {detail}[/]{skip_marker}")

            if disabled > 0:
                stderr.print(f"  [dim]({disabled} additional server(s) disabled)[/]")
            stderr.print()
        return

    # Analyze
    analyses = []
    for adapter in adapters_to_run:
        stderr.print(f"[bold]Analyzing {adapter.name}...[/]")
        try:
            analysis = await analyze_adapter(adapter, options)
            analyses.append(analysis)
        except Exception as exc:
            stderr.print(f"  [red]✗ Failed: {exc}[/]")

    report = build_report(analyses)

    # Exit code 2 when all probes failed (distinct from exit 1 = no configs found)
    if analyses and all(
        all(s.error for s in a.servers) and a.servers
        for a in analyses
    ):
        stderr.print("\n[red]All server probes failed.[/]")

    # Output
    if options.json_output:
        click.echo(format_json(report))
    elif options.markdown:
        click.echo(format_markdown(report))
    else:
        click.echo(format_table(report))

    # Set exit code after output so the report is still emitted
    if analyses and all(
        all(s.error for s in a.servers) and a.servers
        for a in analyses
    ):
        sys.exit(2)

