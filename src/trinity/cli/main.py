"""Trinity CLI entry point."""
from __future__ import annotations

import click
from rich.console import Console
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
from trinity.process import process_scan_file
from trinity.report.data import gather_report_data
from trinity.report.educational import generate_educational_report
from trinity.report.professional import generate_professional_report
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


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context):
    """Trinity — local-first CTF/HTB recon copilot.

    Run with no arguments to launch the interactive wizard (setup /
    resume a project / start a new one). Every other command below
    still works standalone for anyone who wants to drive directly."""
    if ctx.invoked_subcommand is None:
        conn = connect()
        launch_wizard(conn)


@cli.command()
def init():
    """Initialize the local database and seed the starter knowledge base
    plus the pre-authored command-explanation and error-pattern libraries."""
    from trinity.errors_seed import seed_error_patterns

    conn = connect()
    count = seed(conn)
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

    for fr in result.findings:
        f = fr.finding
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
            console.print(
                f"  [bold green]{m.title}[/bold green]  "
                f"[{color}]\\[{m.severity.upper()}][/{color}]  [dim](score {m.score:.1f}, {m.source})[/dim]"
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
            console.print()


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
    box = get_box_or_fail(conn, box_name)
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
    from trinity.tui.dashboard import run_dashboard

    conn = connect()
    box = get_box_by_name(conn, box_name)
    if box:
        touch_active_box(conn, box.id)

    run_dashboard(box_name, Path(watch_dir).resolve())


@cli.command("setup")
def setup_cmd():
    """Re-run the intro/onboarding walkthrough on demand (intro text +
    theme tip). Doesn't touch any existing project data."""
    from trinity.wizard import run_intro

    conn = connect()
    run_intro(conn)


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

    label = {"rooted": "Rooted! 🎉", "abandoned": "Marked abandoned.", "active": "Marked active."}[status]
    console.print(f"[green]{label}[/green] ({box_name})")
    if status == "rooted":
        console.print(
            "[dim]Nice work. Generate a report with:[/dim]\n"
            f"  [bold]trinity report --box \"{box_name}\"[/bold]"
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
    secondary options."""
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
    elif box.mode == "professional":
        # Professional mode: mode is a lens, not a fork -- same
        # ranking, same data, but the teaching narration is stripped
        # to keep this a fast reference rather than a lesson.
        console.print(f"[dim](run `trinity explain \"{rec.top.command}\"` for a command breakdown)[/dim]")
    else:
        console.print(f"[dim]{rec.why}[/dim]\n")
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
    console.print("[dim]That's normal — parked it. Moving on.[/dim]")

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
    Only asks you to bring in AI help on a genuine cache miss."""
    conn = connect()
    match = find_error_match(conn, error_text)

    if match:
        console.print("[green]From local cache (no tokens spent):[/green]\n")
        console.print(f"[bold]Cause:[/bold] {match.cause}")
        console.print(f"[bold]Fix:[/bold] {match.fix}")
    else:
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


if __name__ == "__main__":
    cli()
