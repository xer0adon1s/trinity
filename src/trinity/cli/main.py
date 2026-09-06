"""Trinity CLI entry point."""
from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from trinity.boxes import get_or_create_box, list_boxes, set_mode
from trinity.db import connect
from trinity.explain import build_escalation_prompt, get_explanation, save_explanation
from trinity.kb.seed import seed
from trinity.match.engine import match_finding
from trinity.parsers.nmap import parse_nmap_xml
from trinity.report.data import gather_report_data
from trinity.report.educational import generate_educational_report
from trinity.report.professional import generate_professional_report
from trinity.suggest.engine import suggest_next_commands
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

    suggestions = suggest_next_commands(conn, box.id)
    if suggestions:
        console.rule("[bold magenta]Suggested next commands[/bold magenta]")
        for s in suggestions:
            cursor = conn.execute(
                "INSERT INTO suggestions (box_id, phase, command, rationale) VALUES (?, ?, ?, ?)",
                (box.id, s.phase, s.command, s.rationale),
            )
            conn.commit()
            log_event(
                conn, box.id, "suggestion", f"suggested: {s.command}",
                phase=s.phase, detail=s.rationale, ref_id=cursor.lastrowid,
            )
            console.print(f"  [bold]{s.command}[/bold]")
            console.print(f"  [dim]{s.rationale}[/dim]")
            console.print(f"  [dim](run `trinity explain \"{s.command}\"` to break this down)[/dim]")
            console.print()


@cli.command("suggest")
@click.option("--box", "box_name", required=True, help="Box name.")
def suggest_cmd(box_name: str):
    """Show suggested next commands for a box, based on findings so far."""
    conn = connect()
    box = get_or_create_box(conn, box_name)
    suggestions = suggest_next_commands(conn, box.id)

    if not suggestions:
        console.print("[dim]No new suggestions — either nothing's been parsed yet, "
                       "or everything obvious has already been suggested.[/dim]")
        return

    for s in suggestions:
        cursor = conn.execute(
            "INSERT INTO suggestions (box_id, phase, command, rationale) VALUES (?, ?, ?, ?)",
            (box.id, s.phase, s.command, s.rationale),
        )
        conn.commit()
        log_event(
            conn, box.id, "suggestion", f"suggested: {s.command}",
            phase=s.phase, detail=s.rationale, ref_id=cursor.lastrowid,
        )
        console.print(f"[bold]{s.command}[/bold]")
        console.print(f"[dim]{s.rationale}[/dim]\n")


@cli.command("explain")
@click.argument("command")
@click.option("--box", "box_name", default=None, help="Box name, to log this explanation to its timeline.")
def explain_cmd(command: str, box_name: str | None):
    """Explain a command in plain (ELI5) terms. Checks the local cache
    first — free and instant if this exact command has been explained
    before, on any box, ever. Only asks you to bring in AI help on a
    genuine cache miss."""
    conn = connect()
    cached = get_explanation(conn, command)

    if cached:
        console.print("[green]From local cache (no tokens spent):[/green]\n")
        console.print(cached)
    else:
        console.print("[yellow]Not in the local cache yet.[/yellow] Bring this to your AI assistant:\n")
        console.print(f"[dim]{'-' * 60}[/dim]")
        console.print(build_escalation_prompt(command))
        console.print(f"[dim]{'-' * 60}[/dim]\n")
        console.print(
            "Once you have an answer, save it locally with:\n"
            f"  [bold]trinity cache-explanation \"{command}\" \"<the explanation>\"[/bold]"
        )
        return

    if box_name:
        box = get_or_create_box(conn, box_name)
        log_event(conn, box.id, "explanation", f"explained: {command}", detail=cached)


@cli.command("cache-explanation")
@click.argument("command")
@click.argument("explanation")
def cache_explanation_cmd(command: str, explanation: str):
    """Save an ELI5 explanation for a command to the local cache, so it
    never needs to be re-explained (by anyone, on any box) again."""
    conn = connect()
    save_explanation(conn, command, explanation)
    console.print(f"[green]Cached.[/green] `trinity explain \"{command}\"` will be instant from now on.")


@cli.command("engagement-set")
@click.option("--box", "box_name", required=True, help="Box name.")
@click.option("--client", "client_name", default=None)
@click.option("--scope", default=None)
@click.option("--auth-ref", "authorization_ref", default=None, help="Authorization reference (e.g. HTB username, signed letter ref).")
@click.option("--tester", "tester_name", default=None)
@click.option("--start", "start_date", default=None)
@click.option("--end", "end_date", default=None)
@click.option("--notes", default=None)
def engagement_set_cmd(box_name, client_name, scope, authorization_ref, tester_name, start_date, end_date, notes):
    """Set engagement front matter for a box (used in professional-mode
    reports). Only overwrites fields you actually pass — safe to call
    repeatedly to fill in details as they become known."""
    conn = connect()
    box = get_or_create_box(conn, box_name)

    existing = conn.execute(
        "SELECT * FROM engagement_meta WHERE box_id = ?", (box.id,)
    ).fetchone()
    current = dict(existing) if existing else {}

    updated = {
        "client_name": client_name if client_name is not None else current.get("client_name"),
        "scope": scope if scope is not None else current.get("scope"),
        "authorization_ref": authorization_ref if authorization_ref is not None else current.get("authorization_ref"),
        "tester_name": tester_name if tester_name is not None else current.get("tester_name"),
        "start_date": start_date if start_date is not None else current.get("start_date"),
        "end_date": end_date if end_date is not None else current.get("end_date"),
        "notes": notes if notes is not None else current.get("notes"),
    }

    conn.execute(
        """
        INSERT INTO engagement_meta (box_id, client_name, scope, authorization_ref, tester_name, start_date, end_date, notes)
        VALUES (:box_id, :client_name, :scope, :authorization_ref, :tester_name, :start_date, :end_date, :notes)
        ON CONFLICT(box_id) DO UPDATE SET
            client_name = excluded.client_name, scope = excluded.scope,
            authorization_ref = excluded.authorization_ref, tester_name = excluded.tester_name,
            start_date = excluded.start_date, end_date = excluded.end_date, notes = excluded.notes
        """,
        {"box_id": box.id, **updated},
    )
    conn.commit()
    console.print(f"[green]Engagement details updated for {box_name}.[/green]")


@cli.command("report")
@click.option("--box", "box_name", required=True, help="Box name.")
@click.option("--mode", default=None, type=click.Choice(["educational", "professional"]),
              help="Override the box's stored mode for this report only.")
@click.option("--output", "output_path", default=None, type=click.Path(), help="Write to a file instead of stdout.")
def report_cmd(box_name: str, mode: str | None, output_path: str | None):
    """Generate a report for a box: an educational walkthrough or a
    professional pentest deliverable, read from the same timeline data
    either way — mode only changes the formatting."""
    conn = connect()
    box = get_or_create_box(conn, box_name)
    effective_mode = mode or box.mode

    data = gather_report_data(conn, box.id)
    if effective_mode == "professional":
        content = generate_professional_report(data)
    else:
        content = generate_educational_report(data)

    if output_path:
        from pathlib import Path
        Path(output_path).write_text(content)
        console.print(f"[green]Report written to {output_path}[/green] ({effective_mode} mode).")
    else:
        # Report content is Markdown, not Rich markup — printing it through
        # Rich's normal path would misinterpret things like "[fill in]" as
        # bracket-tag syntax and silently eat the text. Print it raw.
        console.print(content, markup=False, highlight=False)


if __name__ == "__main__":
    cli()
