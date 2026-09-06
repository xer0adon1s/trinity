"""Trinity CLI entry point."""
from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from trinity.boxes import get_or_create_box, list_boxes, set_mode
from trinity.db import connect
from trinity.kb.seed import seed
from trinity.match.engine import match_finding
from trinity.parsers.nmap import parse_nmap_xml
from trinity.timeline import log_event

console = Console()

_SEVERITY_COLOR = {
    "critical": "bold red",
    "high": "red",
    "medium": "yellow",
    "low": "cyan",
    "info": "dim",
}


@click.group()
def cli():
    """Trinity — local-first CTF/HTB recon copilot."""


@cli.command()
def init():
    """Initialize the local database and seed the starter knowledge base."""
    conn = connect()
    count = seed(conn)
    console.print(f"[green]Trinity DB ready.[/green] Seeded {count} new KB entries.")


@cli.command("box-list")
def box_list():
    """List all boxes Trinity knows about."""
    conn = connect()
    boxes = list_boxes(conn)
    if not boxes:
        console.print("[dim]No boxes yet. Run a parse command with --box to create one.[/dim]")
        return

    table = Table()
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Target")
    table.add_column("Platform")
    table.add_column("Mode")
    table.add_column("Status")
    for box in boxes:
        table.add_row(str(box.id), box.name, box.target or "-", box.platform or "-", box.mode, box.status)
    console.print(table)


@cli.command("box-mode")
@click.argument("box_name")
@click.argument("mode", type=click.Choice(["educational", "professional"]))
def box_mode(box_name: str, mode: str):
    """Set a box's mode: educational or professional."""
    conn = connect()
    box = get_or_create_box(conn, box_name)
    set_mode(conn, box.id, mode)
    console.print(f"[green]{box_name}[/green] set to [bold]{mode}[/bold] mode.")


@cli.command("parse-nmap")
@click.argument("xml_path", type=click.Path(exists=True))
@click.option("--box", "box_name", required=True, help="Box name (created if new).")
@click.option("--target", default=None, help="Target IP/hostname (stored on first creation).")
@click.option("--platform", default=None, type=click.Choice(["htb", "thm", "ctf", "other"]))
@click.option("--mode", default="educational", type=click.Choice(["educational", "professional"]))
def parse_nmap_cmd(xml_path: str, box_name: str, target: str | None, platform: str | None, mode: str):
    """Parse an nmap XML scan, match every finding against the local KB,
    and persist findings + matches + a timeline entry for the box."""
    conn = connect()
    box = get_or_create_box(conn, box_name, target=target, platform=platform, mode=mode)

    findings = parse_nmap_xml(xml_path)
    if not findings:
        console.print("[yellow]No open ports found in that scan.[/yellow]")
        return

    log_event(
        conn, box.id, "scan", f"nmap scan parsed: {len(findings)} open port(s) found",
        phase="recon", detail=str(xml_path),
    )

    for finding in findings:
        cursor = conn.execute(
            """
            INSERT INTO findings
                (box_id, source_tool, kind, host, port, service, product, version, detail, raw_ref)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                box.id, finding.source_tool, finding.kind, finding.host, finding.port,
                finding.service, finding.product, finding.version, finding.detail, finding.raw_ref,
            ),
        )
        conn.commit()
        finding_id = cursor.lastrowid

        header = f"[bold cyan]{finding.host}:{finding.port}[/bold cyan] {finding.service or '?'}"
        if finding.product:
            header += f" ({finding.product} {finding.version or ''})"
        console.rule(header)

        matches = match_finding(conn, finding)
        if not matches:
            console.print(
                "  [dim]No local match — this would be a candidate for AI escalation.[/dim]"
            )
            log_event(
                conn, box.id, "finding", f"{finding.host}:{finding.port} — no local match",
                phase="recon", ref_id=finding_id,
            )
            continue

        conn.execute("UPDATE findings SET matched = 1 WHERE id = ?", (finding_id,))
        conn.commit()

        for m in matches:
            color = _SEVERITY_COLOR.get(m.severity, "white")
            console.print(
                f"  [bold green]{m.title}[/bold green]  "
                f"[{color}]\\[{m.severity.upper()}][/{color}]  [dim](score {m.score:.1f}, {m.source})[/dim]"
            )
            console.print(f"  {m.summary}")
            if m.detail:
                console.print(f"  [dim]{m.detail}[/dim]")
            console.print()

        top = matches[0]
        log_event(
            conn, box.id, "match",
            f"{finding.host}:{finding.port} matched: {top.title}",
            phase="recon", detail=top.summary, severity=top.severity, ref_id=finding_id,
        )


if __name__ == "__main__":
    cli()
