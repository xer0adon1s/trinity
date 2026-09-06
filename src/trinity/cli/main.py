"""Trinity CLI entry point."""
from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from trinity.db import connect
from trinity.kb.seed import seed
from trinity.match.engine import match_finding
from trinity.parsers.nmap import parse_nmap_xml

console = Console()


@click.group()
def cli():
    """Trinity — local-first CTF/HTB recon copilot."""


@cli.command()
def init():
    """Initialize the local database and seed the starter knowledge base."""
    conn = connect()
    count = seed(conn)
    console.print(f"[green]Trinity DB ready.[/green] Seeded {count} new KB entries.")


@cli.command("parse-nmap")
@click.argument("xml_path", type=click.Path(exists=True))
def parse_nmap_cmd(xml_path: str):
    """Parse an nmap XML scan and match every finding against the local KB."""
    conn = connect()
    findings = parse_nmap_xml(xml_path)

    if not findings:
        console.print("[yellow]No open ports found in that scan.[/yellow]")
        return

    for finding in findings:
        table = Table(show_header=False, box=None, padding=(0, 1))
        header = f"[bold cyan]{finding.host}:{finding.port}[/bold cyan] {finding.service or '?'}"
        if finding.product:
            header += f" ({finding.product} {finding.version or ''})"
        console.rule(header)

        matches = match_finding(conn, finding)
        if not matches:
            console.print(
                "  [dim]No local match — this would be a candidate for AI escalation.[/dim]"
            )
            continue

        for m in matches:
            console.print(f"  [bold green]{m.title}[/bold green]  [dim](score {m.score:.1f}, {m.source})[/dim]")
            console.print(f"  {m.summary}")
            if m.detail:
                console.print(f"  [dim]{m.detail}[/dim]")
            console.print()


if __name__ == "__main__":
    cli()
