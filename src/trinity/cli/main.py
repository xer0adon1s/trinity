"""Trinity CLI entry point."""
from __future__ import annotations

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from trinity.boxes import get_box_or_fail, get_or_create_box, list_boxes, set_mode, set_status, touch_active_box
from trinity.coach import get_recommendation, set_accepted
from trinity.db import connect
from trinity.errors import build_error_escalation_prompt, find_error_match, save_error_fix
from trinity.explain import build_escalation_prompt, get_explanation, save_explanation
from trinity.explain_seed.combine import seed_all as seed_all_explanations
from trinity.hints import get_hint
from trinity.kb.seed import seed
from trinity.platform_registry import get_platform, list_platform_ids, resolve_theme
from trinity.process import process_ad_file, process_autorecon_results, process_scan_file
from trinity.report.data import gather_report_data
from trinity.report.render import render_report
from trinity.sharing import is_sharing_enabled, set_sharing_enabled, write_share_bundle
from trinity.suggest.engine import suggest_next_commands
from trinity.timeline import log_event
from trinity.wizard import launch as launch_wizard
from trinity.wordlists import NO_WORDLIST_GUIDANCE

console = Console()

_SEVERITY_COLOR = {
    "critical": "bold red",
    "high": "red",
    "medium": "yellow",
    "low": "cyan",
    "info": "dim",
}

# Confidence labels answer a DIFFERENT question than severity: not "how
# bad is this if true" but "how sure is Trinity this is the right next
# step." See KBMatch.confidence in match/engine.py for the derivation.
# Kept as plain bracketed text (not colored as loud as severity) so the
# two signals stay visually distinct rather than competing for the same
# red/yellow/green attention.
_CONFIDENCE_LABEL = {
    "confirmed": "confirmed match",
    "likely": "likely match",
    "best_guess": "best guess — unreviewed searchsploit hit",
}


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context):
    """Trinity — local-first CTF/HTB recon copilot.

    Run with no arguments to launch the interactive wizard (setup /
    resume a project / start a new one). Every other command below
    still works standalone for anyone who wants to drive directly."""
    _sync_external_sources()

    if ctx.invoked_subcommand is None:
        conn = connect()
        launch_wizard(conn)


def _sync_external_sources() -> None:
    """Update Framework Part 1 (docs/UPDATE_FRAMEWORK.md): silent,
    automatic, on-launch sync of external data sources. Runs on every
    invocation of the group callback (i.e. every command), but
    run_sync_if_due()'s own min-interval check means it's a cheap
    sync_state SELECT on the vast majority of those, not an actual
    network hit. Any failure here must never surface to the operator
    or block a normal command -- caught defensively, same "degrade to
    local" contract as vpn.py's VPN check."""
    try:
        from trinity.gtfobins import sync as sync_gtfobins
        from trinity.update_sync import run_sync_if_due

        conn = connect()
        run_sync_if_due(conn, "gtfobins", sync_gtfobins)
    except Exception:  # noqa: BLE001 -- launch-time sync must never break a command
        pass


@cli.command()
def init():
    """Initialize the local database and seed the starter knowledge base
    plus the pre-authored command-explanation and error-pattern libraries."""
    from trinity.errors_seed import seed_error_patterns

    conn = connect()
    from trinity.kb.ad_seed import seed as seed_ad

    count = seed(conn) + seed_ad(conn)
    explain_count = seed_all_explanations(conn)
    error_count = seed_error_patterns(conn)
    console.print(f"[green]Trinity DB ready.[/green] Seeded {count} new KB entries, "
                  f"{explain_count} new command explanations, and {error_count} new error patterns.")


@cli.command("seed-explanations")
def seed_explanations_cmd():
    """(Re-)seed the pre-authored command-explanation library. Safe to
    run any time — never overwrites an explanation you've already
    cached (e.g. via the normal explain/cache-explanation flow)."""
    conn = connect()
    count = seed_all_explanations(conn)
    console.print(f"[green]Seeded {count} new command explanations[/green] "
                  f"({'nothing new to add' if count == 0 else 'library up to date'}).")


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
    box = get_box_or_fail(conn, box_name)
    set_mode(conn, box.id, mode)
    console.print(f"[green]{box_name}[/green] set to [bold]{mode}[/bold] mode.")


@cli.command("parse-nmap")
@click.argument("xml_path", type=click.Path(exists=True))
@click.option("--box", "box_name", required=True, help="Box name (created if new).")
@click.option("--target", default=None, help="Target IP/hostname (stored on first creation).")
@click.option("--platform", default=None, type=click.Choice(list_platform_ids()))
@click.option("--mode", default="educational", type=click.Choice(["educational", "professional"]))
def parse_nmap_cmd(xml_path: str, box_name: str, target: str | None, platform: str | None, mode: str):
    """Parse an nmap XML scan, match every finding against the local KB,
    and persist findings + matches + a timeline entry for the box."""
    from pathlib import Path

    conn = connect()
    box = get_or_create_box(conn, box_name, target=target, platform=platform, mode=mode)
    touch_active_box(conn, box.id)

    result = process_scan_file(conn, box.id, Path(xml_path))
    if result is None:
        console.print(
            "[yellow]That file wasn't recognized as nmap XML output "
            "(or any other known scan format).[/yellow]"
        )
        return
    if not result.findings:
        console.print("[yellow]No open ports found in that scan.[/yellow]")
        return

    # Synthetic, non-port-based findings (e.g. the AD engine's
    # domain-controller detection, which summarizes MULTIPLE ports into
    # one derived fact rather than describing a single port) have no
    # real port/service to put in the normal "host:port service"
    # header -- rendering them through that template produces a
    # nonsense-looking line like "10.10.10.161:None ?" that reads as a
    # parser bug to anyone watching the terminal, even though the
    # AD-aware suggestions underneath are correct. Give them their own
    # header instead. Purely cosmetic -- does not touch matching,
    # scoring, or suggestion logic.
    _SYNTHETIC_FINDING_LABELS = {
        "ad_domain_controller": "Active Directory domain controller detected",
        "ldap_anon": "Anonymous LDAP bind result",
        "asrep_hash": "AS-REP roastable account found",
        "kerberoastable_account": "Kerberoastable service account found",
    }

    for fr in result.findings:
        f = fr.finding
        synthetic_label = _SYNTHETIC_FINDING_LABELS.get(f.kind)
        if synthetic_label:
            header = f"[bold cyan]{synthetic_label}[/bold cyan]"
            if f.detail:
                header += f" — {f.detail}"
        else:
            header = f"[bold cyan]{f.host}:{f.port}[/bold cyan] {f.service or '?'}"
            if f.product:
                header += f" ({f.product} {f.version or ''})"
        console.rule(header)

        if not fr.matches:
            console.print(
                "  [dim]No local match — this would be a candidate for AI escalation.[/dim]"
            )
            continue

        for m in fr.matches:
            color = _SEVERITY_COLOR.get(m.severity, "white")
            confidence_label = _CONFIDENCE_LABEL.get(m.confidence, m.confidence)
            console.print(
                f"  [bold green]{m.title}[/bold green]  "
                f"[{color}]\\[{m.severity.upper()}][/{color}]  [dim]({confidence_label}; score {m.score:.1f}, {m.source})[/dim]"
            )
            console.print(f"  {m.summary}")
            if m.detail:
                console.print(f"  [dim]{m.detail}[/dim]")
            console.print()

    if result.suggestions:
        console.rule("[bold magenta]Suggested next commands[/bold magenta]")
        for command in result.suggestions:
            console.print(f"  [bold]{command}[/bold]")
            console.print(f"  [dim](run `trinity explain \"{command}\"` to break this down)[/dim]")


@cli.command("parse-ad")
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@click.option("--box", "box_name", required=True, help="Box name (created if new).")
@click.option("--target", default=None, help="Target IP/hostname (stored on first creation).")
@click.option("--platform", default=None, type=click.Choice(list_platform_ids()))
@click.option("--mode", default="educational", type=click.Choice(["educational", "professional"]))
def parse_ad_cmd(path: str, box_name: str, target: str | None, platform: str | None, mode: str):
    """Parse ldapsearch, Impacket GetNPUsers.py, or GetUserSPNs.py output
    the operator captured themselves. One command, dispatched by file
    shape — Trinity never launches those tools."""
    from pathlib import Path

    conn = connect()
    box = get_or_create_box(conn, box_name, target=target, platform=platform, mode=mode)
    touch_active_box(conn, box.id)

    result = process_ad_file(conn, box.id, Path(path))
    if not result.findings:
        console.print(
            "[yellow]That file wasn't recognized as ldapsearch, "
            "GetNPUsers.py, or GetUserSPNs.py output.[/yellow]"
        )
        return

    for fr in result.findings:
        f = fr.finding
        header = f"[bold cyan]{f.kind}[/bold cyan]"
        if f.detail:
            header += f" {f.detail}"
        console.rule(header)
        if not fr.matches:
            console.print(
                "  [dim]No local match — this would be a candidate for AI escalation.[/dim]"
            )
            continue
        for m in fr.matches:
            color = _SEVERITY_COLOR.get(m.severity, "white")
            confidence_label = _CONFIDENCE_LABEL.get(m.confidence, m.confidence)
            console.print(
                f"  [bold green]{m.title}[/bold green]  "
                f"[{color}]\\[{m.severity.upper()}][/{color}]  [dim]({confidence_label}; score {m.score:.1f}, {m.source})[/dim]"
            )
            console.print(f"  {m.summary}")
            if m.detail:
                console.print(f"  [dim]{m.detail}[/dim]")
            console.print()

    if result.suggestions:
        console.rule("[bold magenta]Suggested next commands[/bold magenta]")
        for command in result.suggestions:
            console.print(f"  [bold]{command}[/bold]")
            console.print(f"  [dim](run `trinity explain \"{command}\"` to break this down)[/dim]")


@cli.command("parse-autorecon")
@click.argument("results_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--box", "box_name", required=True, help="Box name (created if new).")
@click.option("--target", default=None, help="Target IP/hostname (stored on first creation).")
@click.option("--platform", default=None, type=click.Choice(list_platform_ids()))
@click.option("--mode", default="educational", type=click.Choice(["educational", "professional"]))
def parse_autorecon_cmd(
    results_dir: str, box_name: str, target: str | None, platform: str | None, mode: str
):
    """Walk an AutoRecon results directory (the operator ran AutoRecon
    themselves, in their own terminal pane -- Trinity never launches it)
    and parse every recognized scan file inside it the same way
    `parse-nmap` parses one nmap XML file: match every finding against
    the local KB, and persist findings + matches + a timeline entry for
    the box. Point this at the per-target results directory AutoRecon
    created (the one containing a `scans/` subdirectory), e.g.
    `results/10.10.10.3/`."""
    from pathlib import Path

    conn = connect()
    box = get_or_create_box(conn, box_name, target=target, platform=platform, mode=mode)
    touch_active_box(conn, box.id)

    result, skipped = process_autorecon_results(conn, box.id, Path(results_dir))

    if not result.findings:
        console.print(
            "[yellow]No recognized scan output found under that AutoRecon "
            "results directory (or none of it parsed to any findings).[/yellow]"
        )
    else:
        for fr in result.findings:
            f = fr.finding
            header = f"[bold cyan]{f.host or '?'}"
            if f.port:
                header += f":{f.port}[/bold cyan] {f.service or '?'}"
            else:
                header += f"[/bold cyan] {f.path or f.kind}"
            if f.product:
                header += f" ({f.product} {f.version or ''})"
            console.rule(header)

            if not fr.matches:
                console.print(
                    "  [dim]No local match — this would be a candidate for AI escalation.[/dim]"
                )
                continue

            for m in fr.matches:
                color = _SEVERITY_COLOR.get(m.severity, "white")
                confidence_label = _CONFIDENCE_LABEL.get(m.confidence, m.confidence)
                console.print(
                    f"  [bold green]{m.title}[/bold green]  "
                    f"[{color}]\\[{m.severity.upper()}][/{color}]  [dim]({confidence_label}; score {m.score:.1f}, {m.source})[/dim]"
                )
                console.print(f"  {m.summary}")
                if m.detail:
                    console.print(f"  [dim]{m.detail}[/dim]")
                console.print()

        if result.suggestions:
            console.rule("[bold magenta]Suggested next commands[/bold magenta]")
            for command in result.suggestions:
                console.print(f"  [bold]{command}[/bold]")
                console.print(f"  [dim](run `trinity explain \"{command}\"` to break this down)[/dim]")

    if skipped:
        console.rule("[dim]Skipped files (no parser / unrecognized)[/dim]")
        for note in skipped:
            console.print(f"  [dim]{note}[/dim]")


@cli.command("suggest")
@click.option("--box", "box_name", required=True, help="Box name.")
def suggest_cmd(box_name: str):
    """Show suggested next commands for a box, based on findings so far."""
    conn = connect()
    box = get_box_or_fail(conn, box_name)
    suggestions = suggest_next_commands(conn, box.id)

    if not suggestions:
        console.print("[dim]No new suggestions — either nothing's been parsed yet, "
                       "or everything obvious has already been suggested.[/dim]")
        return

    for s in suggestions:
        cursor = conn.execute(
            "INSERT INTO suggestions (box_id, phase, command, rationale, nudge, required_tool, finding_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (box.id, s.phase, s.command, s.rationale, s.nudge, s.required_tool, s.finding_id),
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
    before, on any box, ever. On a genuine cache miss, tries the Agent
    Harness (docs/AGENT_HARNESS.md) automatically: if an agent CLI is
    detected, asks it directly and queues the answer for review
    (`trinity intake approve/reject`) rather than trusting it outright.
    Falls back to the manual copy-paste flow if no agent is found."""
    conn = connect()
    cached = get_explanation(conn, command)

    if cached:
        console.print("[green]From local cache (no tokens spent):[/green]\n")
        console.print(cached)
    else:
        from trinity.agent_harness import ask_agent
        from trinity.intake import submit_candidate

        answer, agent_name = ask_agent(build_escalation_prompt(command))
        if answer:
            candidate_id = submit_candidate(
                conn, "explanation", {"command": command, "explanation": answer}, "agent_harness",
            )
            console.print(f"[yellow]Not in the local cache yet — asked {agent_name} for you.[/yellow]\n")
            console.print(f"[dim]{'-' * 60}[/dim]")
            console.print(f"[bold]AI DRAFT — UNVERIFIED[/bold] (candidate #{candidate_id}, pending review)\n")
            console.print(answer)
            console.print(f"[dim]{'-' * 60}[/dim]\n")
            console.print(
                "[dim]Not cached yet — review and approve it first:[/dim]\n"
                f"  [bold]trinity intake approve {candidate_id}[/bold]"
            )
            return
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
@click.option("--classification", default=None, help="e.g. TLP:CLEAR / Confidential")
@click.option("--version", "report_version", default=None, help="Report version string.")
@click.option("--distribution", default=None, help="Who may receive the deliverable.")
def engagement_set_cmd(
    box_name, client_name, scope, authorization_ref, tester_name, start_date, end_date,
    notes, classification, report_version, distribution,
):
    """Set engagement front matter for a box (used in professional-mode
    reports). Only overwrites fields you actually pass — safe to call
    repeatedly to fill in details as they become known."""
    conn = connect()
    box = get_box_or_fail(conn, box_name)

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
        "classification": classification if classification is not None else current.get("classification"),
        "report_version": report_version if report_version is not None else current.get("report_version"),
        "distribution": distribution if distribution is not None else current.get("distribution"),
    }

    conn.execute(
        """
        INSERT INTO engagement_meta (box_id, client_name, scope, authorization_ref, tester_name,
            start_date, end_date, notes, classification, report_version, distribution)
        VALUES (:box_id, :client_name, :scope, :authorization_ref, :tester_name, :start_date,
            :end_date, :notes, :classification, :report_version, :distribution)
        ON CONFLICT(box_id) DO UPDATE SET
            client_name = excluded.client_name, scope = excluded.scope,
            authorization_ref = excluded.authorization_ref, tester_name = excluded.tester_name,
            start_date = excluded.start_date, end_date = excluded.end_date, notes = excluded.notes,
            classification = excluded.classification, report_version = excluded.report_version,
            distribution = excluded.distribution
        """,
        {"box_id": box.id, **updated},
    )
    conn.commit()
    console.print(f"[green]Engagement details updated for {box_name}.[/green]")


@cli.command("engagement-show")
@click.option("--box", "box_name", required=True)
def engagement_show_cmd(box_name: str):
    """PROTOTYPE. Print engagement front matter for a box."""
    conn = connect()
    box = get_box_or_fail(conn, box_name)
    row = conn.execute(
        "SELECT * FROM engagement_meta WHERE box_id = ?", (box.id,)
    ).fetchone()
    if row is None:
        console.print(f"[dim]No engagement front matter for {box_name}. Use trinity engagement-set.[/dim]")
        return
    for key in row.keys():
        if key == "box_id":
            continue
        console.print(f"{key}: {row[key] or '—'}")


@cli.command("recap")
@click.option("--box", "box_name", required=True, help="Box name.")
def recap_cmd(box_name: str):
    """A short, personal end-of-box (or mid-box) summary: phases
    touched, techniques encountered, loot recorded, times you got
    stuck. Not a report (see `trinity report`) and not gamified (no
    points/streaks/badges) -- just an honest glance-back at one box,
    for your own study record."""
    from trinity.recap import build_recap, render_recap

    conn = connect()
    box = get_box_or_fail(conn, box_name)
    recap = build_recap(conn, box.id)
    console.print(render_recap(recap), markup=False, highlight=False)


@cli.command("show-me")
@click.option("--box", "box_name", required=True, help="Box name (must have a target set).")
@click.option("--milestone", required=True,
              type=click.Choice(["foothold", "privesc_to_user", "privesc_to_root"]),
              help="The single milestone to attempt live, in Trinity's own session.")
def show_me_cmd(box_name: str, milestone: str):
    """Show Me Mode (docs/SHOW_ME_MODE.md): Trinity's own agent
    attempts ONE step live, in ITS OWN session, against this box's
    target -- never your terminal. Always-available, no stuck-signal
    gate required (break-glass in philosophy, not in access). First
    use requires a one-time authorization acknowledgment. Every run is
    disclosed and permanently recorded -- the resulting report always
    shows when/whether AI assistance was used, this cannot be turned
    off.

    This is Assimilator's LIVE trigger (docs/ASSIMILATOR_PROJECT.md):
    if the step succeeds, Trinity checks whether the answer was
    already sitting in the local KB and the routing just missed it --
    if so, you're told that directly instead of it being logged as new
    knowledge.
    """
    from trinity.show_me import (
        ATTESTATION_TEXT, build_disclosure, has_attestation, record_attestation, run_show_me,
    )

    raise click.ClickException(
        "Show Me Mode is QUARANTINED as of the 2026-09-07 independent code review "
        "(Cursor + Claude Code CLI, see findings/full_review_cursor.md and "
        "findings/full_review_claude.md, and docs/SHOW_ME_MODE_QUARANTINE.md for the "
        "full findings + fix plan). It is disabled at both this CLI entry point and "
        "the TUI Tools menu until a corrected version ships. The code is intact for "
        "reference, not deleted."
    )

    conn = connect()
    box = get_box_or_fail(conn, box_name)

    if not box.target:
        raise click.ClickException(
            f"Box '{box_name}' has no target set -- Show Me Mode needs a real target to run against."
        )

    if not has_attestation(conn):
        console.print(Panel(ATTESTATION_TEXT, title="Authorization", border_style="yellow"))
        if not Confirm.ask("I understand and agree", default=False):
            console.print("[dim]Not proceeding.[/dim]")
            return
        record_attestation(conn)

    from trinity.agent_harness import detect_agent
    agent = detect_agent()
    disclosure = build_disclosure(agent.name if agent else None, milestone)
    console.print(Panel(disclosure.banner, title="Show Me Mode", border_style="magenta"))
    if not Confirm.ask("\nContinue?", default=False):
        console.print("[dim]Not proceeding.[/dim]")
        return

    result = run_show_me(conn, box.id, milestone)

    if result.outcome == "succeeded":
        console.print(Panel(
            f"[bold]Recipe to run yourself:[/bold]\n\n{result.recipe_for_student}",
            title="Show Me Mode — succeeded", border_style="green",
        ))
        console.print(
            "[dim](This does NOT count as your own progress until you run it "
            "yourself. The report will mark this milestone as AI-assisted.)[/dim]"
        )
    elif result.outcome == "already_known":
        console.print(Panel(
            f"[bold]Trinity already knew this:[/bold] {result.already_known_title}\n\n"
            f"Recipe: {result.recipe_for_student}\n\n"
            "This wasn't a new capability gap — the answer was already in "
            "Trinity's local knowledge base. Worth re-checking why the normal "
            "coaching (`trinity next`/`hint`/`explain`) didn't surface it for "
            "you — try those commands again on this finding.",
            title="Show Me Mode — already known", border_style="cyan",
        ))
    else:
        console.print(Panel(
            f"Didn't reach {milestone}." + (f" ({result.stop_reason})" if result.stop_reason else ""),
            title="Show Me Mode — no result", border_style="red",
        ))


@cli.command("doctor")
@click.option("--no-vpn", is_flag=True, help="Skip the VPN check (useful before picking a target).")
def doctor_cmd(no_vpn: bool):
    """One health check: DB reachable, recon tools on PATH, VPN
    status. Read-only -- never installs or fixes anything itself, same
    as every other tool-availability check in Trinity. Also runs
    quietly (failures-only) at the start of `trinity watch`/`trinity
    shoulder` so a missing tool or dead VPN surfaces before it wastes
    your time mid-box."""
    from trinity.doctor import render_doctor, run_doctor

    report = run_doctor(include_vpn=not no_vpn)
    console.print(render_doctor(report), markup=False, highlight=False)


@cli.command("report")
@click.option("--box", "box_name", required=True, help="Box name.")
@click.option("--mode", default=None, type=click.Choice(["educational", "professional", "notebook"]),
              help="Override the box's stored mode for this report only.")
@click.option("--output", "output_path", default=None, type=click.Path(), help="Write to a file instead of stdout.")
def report_cmd(box_name: str, mode: str | None, output_path: str | None):
    """Generate a report for a box: an educational walkthrough or a
    professional pentest deliverable, read from the same timeline data
    either way — mode only changes the formatting."""
    conn = connect()
    box = get_box_or_fail(conn, box_name)
    effective_mode = mode or box.mode

    data = gather_report_data(conn, box.id)
    content = render_report(data, effective_mode)

    if output_path:
        from pathlib import Path
        Path(output_path).write_text(content)
        console.print(f"[green]Report written to {output_path}[/green] ({effective_mode} mode).")
    else:
        # Report content is Markdown, not Rich markup — printing it through
        # Rich's normal path would misinterpret things like "[fill in]" as
        # bracket-tag syntax and silently eat the text. Print it raw.
        console.print(content, markup=False, highlight=False)


@cli.command("watch")
@click.option("--box", "box_name", required=True, help="Box name (must already exist).")
@click.option("--dir", "watch_dir", default=".", type=click.Path(exists=True, file_okay=False),
              help="Directory to watch for new/changed scan output (default: current directory).")
def watch_cmd(box_name: str, watch_dir: str):
    """Launch the live watch-mode dashboard: watches a directory for new
    scan output (nmap XML, gobuster/ffuf/nikto/whatweb/enum4linux-ng),
    auto-parses and matches it the moment it lands, and shows a live
    feed alongside suggested next commands. Meant to run in one terminal
    tile while you run the actual recon tools in an adjacent one — "I
    do" (Trinity narrates) next to "we do" (you run the real tool)."""
    from pathlib import Path

    from trinity.boxes import get_box_by_name
    from trinity.doctor import run_doctor
    from trinity.tui.dashboard import run_dashboard

    conn = connect()
    box = get_box_by_name(conn, box_name)
    if box:
        touch_active_box(conn, box.id)

    doctor_report = run_doctor(include_vpn=True)
    for failure in doctor_report.failures:
        if failure.name.startswith("tool:"):
            continue  # missing tools are handled per-suggestion by coach.py already
        console.print(f"[yellow]doctor: {failure.name} — {failure.detail}[/yellow]")

    run_dashboard(box_name, Path(watch_dir).resolve())


@cli.command("shoulder")
@click.option("--box", "box_name", required=True, help="Box name (must already exist).")
@click.option("--shell", "shell_bin", default=None,
              help="Shell to record (default: $SHELL, falling back to /bin/bash).")
def shoulder_cmd(box_name: str, shell_bin: str | None):
    """Shoulder Mode (docs/SHOULDER_MODE.md): records this ENTIRE
    terminal session (every byte in and out, script(1)-equivalent) to
    a local log file, then scans it for shell/root milestone signals
    when you exit. Meant to run in the SAME pane you're doing the real
    recon/exploitation work in — Trinity is genuinely watching this
    one, not narrating from an adjacent tile like `watch` does. Type
    `exit` (or Ctrl-D) to end the recorded session and see what was
    detected.

    Also runs the Coach subsystem (docs/COACH_SUBSYSTEM_DESIGN.md)
    live alongside recording: if you land a shell (or, later, enter a
    recognized tool session), Trinity narrates/nudges from the SAME
    margin it prints milestone detections in — it only ever reads the
    stream, never types into it.
    """
    import os as _os

    from trinity.boxes import get_box_or_fail
    from trinity.doctor import run_doctor
    from trinity.shell_coach import new_session as new_coach_session
    from trinity.shoulder import apply_milestones, record_session, scan_for_milestones, session_log_path

    conn = connect()
    box = get_box_or_fail(conn, box_name)
    touch_active_box(conn, box.id)

    doctor_report = run_doctor(include_vpn=True)
    for failure in doctor_report.failures:
        if failure.name.startswith("tool:"):
            continue  # missing tools are handled per-suggestion by coach.py already
        console.print(f"[yellow]doctor: {failure.name} — {failure.detail}[/yellow]")

    shell = shell_bin or _os.environ.get("SHELL", "/bin/bash")
    log_path = session_log_path(box_name)

    console.print(f"[bold]Shoulder Mode on.[/bold] Recording this session to {log_path}")
    console.print("[dim]Type `exit` or Ctrl-D when you're done — Trinity will scan for milestones then.[/dim]\n")

    coach = new_coach_session()
    line_buffer = b""

    def on_chunk(data: bytes) -> None:
        nonlocal line_buffer
        line_buffer += data
        while b"\n" in line_buffer:
            raw_line, line_buffer = line_buffer.split(b"\n", 1)
            line = raw_line.decode(errors="replace")
            narration = coach.feed_line(line)
            if narration:
                console.print(f"\n[bold magenta][coach][/bold magenta] {narration}\n")

    record_session(shell, log_path, on_chunk=on_chunk)

    console.print("\n[bold]Shoulder Mode off.[/bold] Scanning session for milestones...")
    text = log_path.read_text(errors="replace")
    hits = scan_for_milestones(text)
    applied = apply_milestones(conn, box.id, hits)

    if not applied:
        console.print("[dim]Nothing new detected this session.[/dim]")
        return
    for hit in applied:
        console.print(f"[green]Detected: {hit.name}[/green] (shell_level -> {hit.shell_level})")


@cli.command("setup")
def setup_cmd():
    """Re-run the intro/onboarding walkthrough on demand (intro text +
    theme tip). Doesn't touch any existing project data."""
    from trinity.wizard import run_intro

    conn = connect()
    run_intro(conn)


@cli.group("nickname")
def nickname_group():
    """Manage the optional hacker-name Trinity greets you with. Off by
    default until you opt in (at `trinity setup` or here)."""


@nickname_group.command("show")
def nickname_show_cmd():
    """Show whether the hacker name is on, and what it's currently set to."""
    from trinity.state import HACKER_NAME, HACKER_NAME_ENABLED, get_state
    from trinity.wizard import get_hacker_name

    conn = connect()
    stored_name = get_state(conn, HACKER_NAME)
    active_name = get_hacker_name(conn)
    if active_name:
        console.print(f"[green]On.[/green] Trinity calls you [bold]{active_name}[/bold].")
    elif stored_name:
        console.print(f"[dim]Off.[/dim] A name is saved ({stored_name!r}) but not active — `trinity nickname on` to re-enable.")
    else:
        console.print("[dim]Off. No name set yet — `trinity nickname set <name>` to pick one.[/dim]")


@nickname_group.command("on")
def nickname_on_cmd():
    """Turn the hacker-name greeting on. If a name was set before
    (even if later turned off), reuses it — no need to retype it."""
    from trinity.state import HACKER_NAME, get_state
    from trinity.wizard import set_hacker_name_enabled

    conn = connect()
    set_hacker_name_enabled(conn, True)
    name = get_state(conn, HACKER_NAME)
    if name:
        console.print(f"[green]On.[/green] Trinity will call you [bold]{name}[/bold] again.")
    else:
        console.print("[green]On[/green] — but no name is set yet. Run `trinity nickname set <name>`.")


@nickname_group.command("off")
def nickname_off_cmd():
    """Turn the hacker-name greeting off. The name itself is kept (not
    erased), so turning it back on later remembers it."""
    from trinity.wizard import set_hacker_name_enabled

    conn = connect()
    set_hacker_name_enabled(conn, False)
    console.print("[dim]Off. Trinity will use generic greetings. `trinity nickname on` to bring it back.[/dim]")


@nickname_group.command("set")
@click.argument("name")
def nickname_set_cmd(name: str):
    """Set (and enable) a hacker name in one step."""
    from trinity.wizard import set_hacker_name

    conn = connect()
    set_hacker_name(conn, name)
    console.print(f"[green]Got it, {name}.[/green]")


@cli.group("notify")
def notify_group():
    """Manage the optional desktop notification on critical matches.
    Off by default until you opt in (at `trinity setup` or here)."""


@notify_group.command("show")
def notify_show_cmd():
    """Show whether desktop notifications are currently on."""
    from trinity.notify import is_notify_enabled

    conn = connect()
    if is_notify_enabled(conn):
        console.print("[green]On.[/green] You'll get a desktop notification on critical matches.")
    else:
        console.print("[dim]Off.[/dim] `trinity notify on` to enable.")


@notify_group.command("on")
def notify_on_cmd():
    """Turn desktop notifications on."""
    from trinity.state import NOTIFY_ENABLED, set_state

    conn = connect()
    set_state(conn, NOTIFY_ENABLED, "1")
    console.print("[green]On.[/green] You'll get a desktop notification on critical matches.")


@notify_group.command("off")
def notify_off_cmd():
    """Turn desktop notifications off."""
    from trinity.state import NOTIFY_ENABLED, set_state

    conn = connect()
    set_state(conn, NOTIFY_ENABLED, "0")
    console.print("[dim]Off.[/dim] `trinity notify on` to re-enable.")


@notify_group.command("test")
def notify_test_cmd():
    """Fire one test notification right now, regardless of the on/off
    toggle -- useful for confirming notify-send actually works on this
    machine before relying on it."""
    from trinity.notify import send_test_notification

    sent = send_test_notification()
    if sent:
        console.print("[green]Sent.[/green] Check your desktop notification area.")
    else:
        console.print("[yellow]Couldn't send it.[/yellow] Is `notify-send` installed?")


@cli.command("box-status")
@click.argument("box_name")
@click.argument("status", type=click.Choice(["active", "rooted", "abandoned"]))
def box_status_cmd(box_name: str, status: str):
    """Mark a box active / rooted / abandoned. Marking a box rooted or
    abandoned closes it out — the next bare `trinity` launch will offer
    to start a new project instead of resuming this one."""
    conn = connect()
    box = get_box_or_fail(conn, box_name)
    set_status(conn, box.id, status)
    log_event(conn, box.id, "milestone", f"box marked {status}")
    # PROTOTYPE (1.6): rooted without a prior `trinity shell` still
    # counts as a root milestone so unlock cards can appear.
    if status == "rooted" and box.shell_level is None:
        from trinity.boxes import set_shell_level
        set_shell_level(conn, box.id, "root")

    label = {"rooted": "Rooted! 🎉", "abandoned": "Marked abandoned.", "active": "Marked active."}[status]
    console.print(f"[green]{label}[/green] ({box_name})")
    if status == "rooted":
        from trinity.unlocks import peek_card
        console.print(
            "[dim]Nice work. Generate a report with:[/dim]\n"
            f"  [bold]trinity report --box \"{box_name}\"[/bold]"
        )
        if peek_card(conn, box.id):
            console.print(
                f"[dim]Optional (skip by default): `trinity unlock --box \"{box_name}\"`[/dim]"
            )


@cli.command("theme")
@click.argument("name", required=False)
@click.option("--omarchy", is_flag=True, help="Use your live Omarchy desktop theme's colors instead of a platform theme.")
def theme_cmd(name: str | None, omarchy: bool):
    """Show or preview a theme. Pass a platform id (htb, thm, ...) to
    preview its colors, or --omarchy to preview your current Omarchy
    desktop theme's colors instead. With no arguments, lists all known
    platform ids."""
    if name is None and not omarchy:
        console.print("[bold]Known platforms:[/bold] " + ", ".join(list_platform_ids()))
        console.print("[dim]Usage: trinity theme <platform> | trinity theme --omarchy[/dim]")
        return

    theme = resolve_theme(name, prefer_omarchy=omarchy)
    if omarchy:
        label = "your Omarchy desktop theme"
    else:
        platform = get_platform(name)
        label = platform.name if platform else f"{name} (unknown platform, using default theme)"
    console.print(f"[bold]{label}[/bold]")
    console.print(f"  accent:     [{theme.accent}]███[/{theme.accent}] {theme.accent}")
    console.print(f"  background: [{theme.background}]███[/{theme.background}] {theme.background}")
    console.print(f"  foreground: [{theme.foreground}]███[/{theme.foreground}] {theme.foreground}")


@cli.command("share-export")
@click.option("--box", "box_name", required=True, help="Box name.")
@click.option("--output", "output_path", default="trinity_share_bundle.json", type=click.Path(),
              help="Where to write the exportable bundle (default: trinity_share_bundle.json).")
@click.option("--enable", is_flag=True, help="Also turn on opt-in sharing for future sessions.")
def share_export_cmd(box_name: str, output_path: str, enable: bool):
    """Export this box's AI-escalation explanations and unmatched
    findings as an anonymized, shareable bundle — nothing is sent
    anywhere automatically. Review the file, then contribute it
    upstream (e.g. via a PR) if you want to help grow the shared KB."""
    from pathlib import Path

    conn = connect()
    box = get_or_create_box(conn, box_name)

    if enable:
        set_sharing_enabled(conn, True)
        console.print("[green]Opt-in sharing enabled.[/green]")

    count = write_share_bundle(conn, box.id, Path(output_path))
    console.print(f"[green]Wrote {count} shareable item(s) to {output_path}.[/green]")
    notebook_path = Path(output_path).with_suffix(".md")
    from trinity.report.data import gather_report_data
    from trinity.report.render import render_report
    notebook_path.write_text(render_report(gather_report_data(conn, box.id), "notebook"))
    console.print(f"[dim]Also wrote a local lab-notebook tear-out: {notebook_path}[/dim]")
    console.print(
        "[dim]Nothing was sent anywhere — review the file, then contribute it "
        "upstream yourself if you'd like to help grow the shared knowledge base.[/dim]"
    )


@cli.command("next")
@click.option("--box", "box_name", required=True, help="Box name.")
def next_cmd(box_name: str):
    """Recommend exactly one next command to run, with the reasoning
    for why it's first — instead of a flat list of equally-weighted
    suggestions. The rest of the valid suggestions are still listed
    underneath as secondary options (annotated installed/not-installed
    once Hole C makes more than one live at once). In professional
    mode, the WHY narration is skipped -- just the command and
    secondary options.

    Advisory content (difficulty note, curiosity-card teaser,
    rabbit-hole nudge, AutoRecon graduation nudge) is arbitrated by
    advisories.py rather than each feature printing directly: only the
    single highest-priority advisory with something to say is shown,
    composed into one flowing sentence rather than stacked as separate
    lines. See docs/FEATURES_BACKLOG.md's "structural fix" note --
    this replaces an earlier flat-line-count-cap plan with real
    arbitration instead of truncation."""
    from trinity.advisories import pick_advisory

    conn = connect()
    box = get_box_or_fail(conn, box_name)

    rec = get_recommendation(conn, box.id)
    if rec is None:
        console.print(
            "[dim]Nothing to recommend yet — either nothing's been parsed for "
            "this box, or every obvious next step has already been suggested.[/dim]"
        )
        return

    console.rule("[bold green]Recommended next[/bold green]")
    console.print(f"[bold]{rec.top.command}[/bold]\n")

    if rec.wordlist_missing:
        console.print(f"[yellow]{NO_WORDLIST_GUIDANCE}[/yellow]\n")

    if rec.tool_missing:
        # `next` is "tell me what to do" -- naming the missing tool here
        # is correct (unlike `hint`, see hint_cmd below, where naming it
        # early would leak the answer). We do NOT early-return: the
        # operator should still see the secondary suggestions while they
        # go install the tool, not just a dead end (see
        # docs/CLAUDE_CURSOR_DEBATE.md Part B.2 -- this early-return used
        # to hide `also_worth_trying` entirely).
        console.print(f"[yellow]{rec.install_guidance}[/yellow]\n")
        console.print(
            "[dim]Once that's installed, just run this same command again -- "
            f"I'll pick up right where we left off: `trinity next --box \"{box_name}\"`[/dim]\n"
        )
        if box.mode != "professional":
            advisory = pick_advisory(conn, box)
            if advisory:
                console.print(f"[dim]{advisory.sentence.capitalize()}.[/dim]\n")
    elif box.mode == "professional":
        # Professional mode: mode is a lens, not a fork -- same
        # ranking, same data, but the teaching narration is stripped
        # to keep this a fast reference rather than a lesson.
        console.print(f"[dim](run `trinity explain \"{rec.top.command}\"` for a command breakdown)[/dim]")
    else:
        why = rec.why
        advisory = pick_advisory(conn, box)
        if advisory:
            # Compose into ONE flowing paragraph rather than a
            # separate stacked line -- the actual point of the
            # arbitration system: one professorial thought, not a
            # bulleted pileup. Lower-case join since the advisory
            # sentence is written as a clause, not a new sentence.
            why = f"{why} And one more thing worth knowing: {advisory.sentence}."
        console.print(f"[dim]{why}[/dim]\n")
        quoted_command = f'"{rec.top.command}"'
        quoted_box = f'"{box_name}"'
        console.print(
            f"[dim](run `trinity explain {quoted_command}` for a command breakdown, "
            f"or `trinity hint --box {quoted_box}` if you want to work it out yourself first)[/dim]"
        )

    console.print(
        f"[dim](done? `trinity did --box \"{box_name}\"`  ·  "
        f"skipping this one? `trinity skip --box \"{box_name}\"`)[/dim]"
    )

    if rec.also_worth_trying:
        console.print()
        console.rule("[dim]Also worth trying[/dim]")
        for s, installed in zip(rec.also_worth_trying, rec.also_worth_trying_installed):
            marker = "" if installed else "  [dim](tool not installed)[/dim]"
            console.print(f"  [dim]{s.command}[/dim]{marker}")


@cli.command("did")
@click.option("--box", "box_name", required=True, help="Box name.")
def did_cmd(box_name: str):
    """Mark the current top recommendation as done. The coach will not
    recommend it again -- `trinity next` moves on to whatever's next
    (Hole A: before this command existed, nothing in Trinity ever set
    a suggestion's accepted flag, so `next` recommended the same
    command forever)."""
    conn = connect()
    box = get_box_or_fail(conn, box_name)

    rec = get_recommendation(conn, box.id)
    if rec is None:
        console.print("[dim]Nothing outstanding to mark done for this box.[/dim]")
        return

    set_accepted(conn, rec.suggestion_id)
    log_event(conn, box.id, "milestone", f"did: {rec.top.command}", phase=rec.top.phase, ref_id=rec.suggestion_id)
    console.print(f"[green]Marked done:[/green] {rec.top.command}")

    next_rec = get_recommendation(conn, box.id)
    if next_rec:
        console.print(f"\n[dim]Next up:[/dim] [bold]{next_rec.top.command}[/bold]")
    else:
        console.print("\n[dim]Nothing else outstanding right now — keep scanning, or check `trinity report`.[/dim]")


@cli.command("skip")
@click.option("--box", "box_name", required=True, help="Box name.")
def skip_cmd(box_name: str):
    """Park the current top recommendation without running it, and move
    on to the next phase-appropriate suggestion. Same underlying
    mechanism as `did` (accepted=1) -- the distinction is in the
    timeline wording, not the schema (see
    docs/CLAUDE_CURSOR_DEBATE.md, Part E item 3)."""
    conn = connect()
    box = get_box_or_fail(conn, box_name)

    rec = get_recommendation(conn, box.id)
    if rec is None:
        console.print("[dim]Nothing outstanding to skip for this box.[/dim]")
        return

    set_accepted(conn, rec.suggestion_id)
    log_event(conn, box.id, "note", f"skipped: {rec.top.command}", phase=rec.top.phase, ref_id=rec.suggestion_id)
    console.print(f"[yellow]Skipped:[/yellow] {rec.top.command}")
    from trinity.deadends import dead_end_line
    console.print(f"[dim]{dead_end_line(rec.top.command)}[/dim]")

    next_rec = get_recommendation(conn, box.id)
    if next_rec:
        console.print(f"\n[dim]Next up:[/dim] [bold]{next_rec.top.command}[/bold]")
    else:
        console.print("\n[dim]Nothing else outstanding right now — keep scanning, or check `trinity report`.[/dim]")


@cli.command("hint")
@click.option("--box", "box_name", required=True, help="Box name.")
def hint_cmd(box_name: str):
    """Get a graduated hint toward the current recommended next step —
    starts with a nudge, escalates to a stronger nudge, then the full
    answer, the more times you ask about the SAME stuck point. A new
    finding/recommendation always starts back at a nudge. In
    professional mode, the Socratic ladder is skipped entirely --
    this just gives the full answer immediately, since a pentest
    deliverable has no use for being coy about the next step."""
    conn = connect()
    box = get_box_or_fail(conn, box_name)

    rec = get_recommendation(conn, box.id)
    if rec is None:
        console.print("[dim]Nothing to hint about yet — nothing's been parsed for this box.[/dim]")
        return

    if box.mode == "professional":
        console.rule("[bold green]Next step[/bold green]")
        console.print(f"{rec.top.rationale}\n\nThe command to run: {rec.top.command}")
        if rec.tool_missing:
            console.print(f"\n[yellow]{rec.install_guidance}[/yellow]")
        return

    hint = get_hint(conn, box.id, rec.suggestion_id, rec.top.phase, rec.top.nudge, rec.top.rationale, rec.top.command)

    # Install guidance NAMES the required tool -- that's the same kind
    # of answer-leak as putting the command in level 2, so it can only
    # appear alongside the full answer (level 3), never earlier. The
    # previous version gated on `get_hint_level(...) >= 2` measured
    # BEFORE this call advanced the level, which meant install guidance
    # actually appeared on the third ask (bundled with L3) despite the
    # comment claiming "level 2+" -- an untested off-by-one in the same
    # family as this project's earlier hint-leak bug. See
    # docs/CLAUDE_CURSOR_DEBATE.md, Part A.3.
    if hint.level == 3:
        if rec.wordlist_missing:
            console.print(f"[yellow]{NO_WORDLIST_GUIDANCE}[/yellow]\n")
        if rec.tool_missing:
            console.rule("[bold yellow]Heads up[/bold yellow]")
            console.print(f"{rec.install_guidance}\n")

    level_label = {1: "Nudge", 2: "Stronger nudge", 3: "Full answer"}[hint.level]
    console.rule(f"[bold yellow]{level_label} ({hint.level}/3)[/bold yellow]")
    console.print(hint.text)
    if hint.level < 3:
        console.print("\n[dim](ask again for a stronger hint on this same step)[/dim]")


@cli.command("error")
@click.argument("error_text")
@click.option("--box", "box_name", default=None, help="Box name, to log this to its timeline.")
def error_cmd(error_text: str, box_name: str | None):
    """Diagnose an error/failure. Checks the local cache first — free
    and instant if this cause has been seen before, on any box, ever.
    On a genuine cache miss, tries the Agent Harness
    (docs/AGENT_HARNESS.md) automatically: if an agent CLI is
    detected, asks it directly and queues the answer for review
    (`trinity intake approve/reject`) rather than trusting it outright.
    Falls back to the manual copy-paste flow if no agent is found."""
    conn = connect()
    match = find_error_match(conn, error_text)

    if match:
        console.print("[green]From local cache (no tokens spent):[/green]\n")
        console.print(f"[bold]Cause:[/bold] {match.cause}")
        console.print(f"[bold]Fix:[/bold] {match.fix}")
    else:
        from trinity.agent_harness import ask_agent
        from trinity.intake import submit_candidate

        answer, agent_name = ask_agent(build_error_escalation_prompt(error_text))
        if answer:
            candidate_id = submit_candidate(
                conn, "error_pattern",
                {"error_text": error_text, "cause": "See AI draft below (unreviewed).", "fix": answer},
                "agent_harness",
            )
            console.print(f"[yellow]Not in the local cache yet — asked {agent_name} for you.[/yellow]\n")
            console.print(f"[dim]{'-' * 60}[/dim]")
            console.print(f"[bold]AI DRAFT — UNVERIFIED[/bold] (candidate #{candidate_id}, pending review)\n")
            console.print(answer)
            console.print(f"[dim]{'-' * 60}[/dim]\n")
            console.print(
                "[dim]Not cached yet — review and approve it first:[/dim]\n"
                f"  [bold]trinity intake approve {candidate_id}[/bold]"
            )
            return
        console.print("[yellow]Not in the local cache yet.[/yellow] Bring this to your AI assistant:\n")
        console.print(f"[dim]{'-' * 60}[/dim]")
        console.print(build_error_escalation_prompt(error_text))
        console.print(f"[dim]{'-' * 60}[/dim]\n")
        console.print(
            "Once you have a confirmed fix, save it locally with:\n"
            f"  [bold]trinity cache-error \"{error_text}\" \"<cause>\" \"<fix>\"[/bold]"
        )
        return

    if box_name:
        box = get_or_create_box(conn, box_name)
        log_event(conn, box.id, "explanation", f"diagnosed error: {error_text[:80]}", detail=match.fix)


@cli.command("cache-error")
@click.argument("error_text")
@click.argument("cause")
@click.argument("fix")
def cache_error_cmd(error_text: str, cause: str, fix: str):
    """Save a confirmed cause/fix for an error to the local cache, so
    it never needs AI escalation again (by anyone, on any box)."""
    conn = connect()
    save_error_fix(conn, error_text, cause, fix)
    console.print("[green]Cached.[/green] `trinity error \"...\"` will catch similar errors from now on.")


@cli.command("shell")
@click.option("--box", "box_name", required=True, help="Box name.")
@click.option("--as", "as_level", required=True, type=click.Choice(["user", "root"]),
              help="What you landed: a user shell or root.")
def shell_cmd(box_name: str, as_level: str):
    """PROTOTYPE (1.6). Tell Trinity you got a shell. Never inferred
    from history. A user shell switches the coach toward privesc; a
    root shell also marks the box rooted. Power-user verb — the wizard
    does not teach this (Hole F)."""
    from trinity.milestones import record_shell
    from trinity.unlocks import peek_card

    conn = connect()
    box = get_box_or_fail(conn, box_name)
    inserted = record_shell(conn, box.id, as_level)
    console.print(f"[green]Recorded a {as_level} shell on {box_name}.[/green]")
    if inserted:
        console.print("[dim]Privilege-escalation checks are now in the deck:[/dim]")
        for command in inserted:
            console.print(f"  [dim]{command}[/dim]")
        console.print(f"[dim]Ask for the next one with `trinity next --box \"{box_name}\"`[/dim]")
    if peek_card(conn, box.id):
        console.print(
            f"[dim]Optional (skip by default): `trinity unlock --box \"{box_name}\"`[/dim]"
        )


@cli.command("unlock")
@click.option("--box", "box_name", required=True, help="Box name.")
@click.option("--take", "action", flag_value="take", default=True,
              help="Show the next available card (default).")
@click.option("--decline", "action", flag_value="decline",
              help="Skip the next card. Declining is the intended default habit.")
def unlock_cmd(box_name: str, action: str):
    """PROTOTYPE (2.1). Optional curiosity card after a milestone.
    Generic pedagogy only — no box spoilers. Power-user verb."""
    from trinity.unlocks import decline_card, peek_card, take_card

    conn = connect()
    box = get_box_or_fail(conn, box_name)
    card = peek_card(conn, box.id)
    if card is None:
        console.print("[dim]Nothing unlocked — land a shell first, or you already handled the cards.[/dim]")
        return

    if action == "decline":
        decline_card(conn, box.id, card.id)
        console.print("[dim]Skipped. You can keep driving.[/dim]")
        return

    taken = take_card(conn, box.id, card.id)
    if taken is None:
        console.print("[dim]Nothing unlocked.[/dim]")
        return
    console.print(f"[bold]{taken.title}[/bold]\n")
    console.print(taken.body)
    console.print(f"\n[dim]source: {taken.source}[/dim]")


@cli.command("loot")
@click.argument("action", type=click.Choice(["add", "list"]))
@click.option("--box", "box_name", required=True, help="Box name.")
@click.option("--kind", type=click.Choice(["credential", "hash", "token", "flag", "other"]),
              help="Required for add.")
@click.option("--value", default=None, help="The secret/flag/hash itself. Required for add.")
@click.option("--note", default=None, help="Optional context (where you found it).")
def loot_cmd(action: str, box_name: str, kind: str | None, value: str | None, note: str | None):
    """Record or list evidence found on a box (credentials, hashes,
    tokens, flags). Power-user verb — not taught by the wizard. Flows
    into the timeline and both report templates."""
    from trinity.loot import add_loot, list_loot

    conn = connect()
    box = get_box_or_fail(conn, box_name)

    if action == "list":
        items = list_loot(conn, box.id)
        if not items:
            console.print(f"[dim]No loot recorded for {box_name}.[/dim]")
            return
        for item in items:
            extra = f"  ({item.note})" if item.note else ""
            console.print(f"[bold]{item.kind}[/bold]  {item.value}{extra}")
        return

    if not kind or not value:
        raise click.ClickException("loot add requires --kind and --value")
    item = add_loot(conn, box.id, kind, value, note=note)
    console.print(f"[green]Recorded {item.kind} on {box_name}.[/green]")


@cli.command("methods")
@click.option("--box", "box_name", default=None, help="Use this project's name as the index key.")
@click.option("--name", "index_name", default=None, help="Retired box name to look up (e.g. Lame).")
def methods_cmd(box_name: str | None, index_name: str | None):
    """PROTOTYPE — Methods Index read-side. Shows distinct public
    method *shapes* for a retired box, each with author + URL.
    Not a walkthrough. Not shown at session start. No fetch pipeline."""
    from trinity.methods import format_index, lookup

    conn = connect()
    name = index_name
    platform = None
    if box_name:
        box = get_box_or_fail(conn, box_name)
        name = name or box.name
        platform = box.platform
    if not name:
        raise click.ClickException("Pass --name Lame or --box <project>.")
    index = lookup(name, platform=platform) or lookup(name)
    if index is None:
        console.print(
            f"[dim]No methods index for {name!r}. This is only populated "
            f"for some retired boxes, by hand. Not a live search.[/dim]"
        )
        return
    console.print(format_index(index), highlight=False)


@cli.command("hash")
@click.argument("value")
def hash_cmd(value: str):
    """Guess a hash/token shape locally (bcrypt, md5crypt, sha512crypt,
    JWT, md5/NTLM/sha1/sha256 by hex length). No network — not a
    replacement for hashid, enough to unstick "found a hex string,
    now what?"."""
    from trinity.hashes import classify_hash

    guess = classify_hash(value)
    console.print(f"[bold]{guess.label}[/bold]  ({guess.confidence})")
    console.print(guess.next_step)


@cli.command("gtfobins")
@click.argument("binary", required=False)
def gtfobins_cmd(binary: str | None):
    """Local GTFOBins lookup (sudo/suid privesc vectors only), synced
    in from the full public GTFOBins dataset via the Update Framework
    (docs/UPDATE_FRAMEWORK.md). Falls back to a small offline seed set
    if the dataset has never synced yet (no network)."""
    from trinity.gtfobins import known_binaries, lookup

    if not binary:
        bins = known_binaries()
        console.print(f"[bold]Known here ({len(bins)}):[/bold] " + ", ".join(bins))
        console.print("[dim]Full catalogue (all vectors, not just sudo/suid): https://gtfobins.github.io/[/dim]")
        return
    hit = lookup(binary)
    if hit is None:
        console.print(
            f"[dim]No local note for {binary!r}. Try the full catalogue: "
            f"https://gtfobins.github.io/gtfobins/{binary.strip().lower()}/[/dim]"
        )
        return
    from rich.markup import escape

    console.print(f"[bold]{hit.binary}[/bold]\n{escape(hit.summary)}\n[dim]{hit.source_url}[/dim]")


@cli.group("intake")
def intake_group():
    """Update Framework review queue: knowledge Trinity's own install
    generated (Agent Harness answers, live-drafted Methods Index
    entries) that hasn't been vetted yet. Nothing here is live until
    reviewed -- see docs/UPDATE_FRAMEWORK.md."""


@intake_group.command("list")
def intake_list_cmd():
    """List pending intake candidates awaiting review."""
    from trinity.intake import list_pending

    conn = connect()
    pending = list_pending(conn)
    if not pending:
        console.print("[dim]Nothing pending review.[/dim]")
        return
    for c in pending:
        console.print(f"[bold]#{c.id}[/bold] ({c.kind}, from {c.source})")
        console.print(f"  [dim]{c.payload}[/dim]")


@intake_group.command("approve")
@click.argument("candidate_id", type=int)
@click.option("--note", default=None, help="Optional reviewer note.")
def intake_approve_cmd(candidate_id: int, note: str | None):
    """Approve a pending candidate: copies it into its real
    destination table (command_explanations/error_patterns/
    kb_entries), same write path as the normal cache flow."""
    from trinity.intake import approve_candidate

    conn = connect()
    try:
        approve_candidate(conn, candidate_id, note=note)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    console.print(f"[green]Approved #{candidate_id}.[/green] Now live in the real cache.")


@intake_group.command("reject")
@click.argument("candidate_id", type=int)
@click.option("--note", default=None, help="Optional reviewer note (e.g. why it was wrong).")
def intake_reject_cmd(candidate_id: int, note: str | None):
    """Reject a pending candidate. Kept for audit, never merged."""
    from trinity.intake import reject_candidate

    conn = connect()
    try:
        reject_candidate(conn, candidate_id, note=note)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    console.print(f"[yellow]Rejected #{candidate_id}.[/yellow]")


if __name__ == "__main__":
    cli()
