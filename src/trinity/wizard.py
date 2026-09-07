"""The onboarding wizard: Trinity's front door. Handles first-run intro,
the startup menu (setup / resume / new project), and per-project mode
selection + VPN check. Built with Rich prompts -- linear, conversational,
scrollback-friendly -- as opposed to the Textual watch-mode dashboard,
which is a live full-screen app for actually working a box. Wizard gets
you in the door; the dashboard is where you work.

Core philosophy: let people drive the car before they have to build the
car. Curiosity about the engine can come later -- the wizard's job is
to get someone cracking their first box with as few questions as
honestly possible, not to make them fill out a form first.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt

from trinity.boxes import Box, create_box, get_box, touch_active_box
from trinity.platform_registry import get_platform, list_platform_ids
from trinity.state import (
    ACTIVE_BOX_ID,
    HACKER_NAME,
    HACKER_NAME_ENABLED,
    NOTIFY_ENABLED,
    SETUP_DONE,
    get_state,
    set_state,
)
from trinity.vpn import check_vpn

console = Console()

INTRO_TEXT = (
    "Trinity is a local-first recon copilot for CTF/HTB/TryHackMe-style practice,\n"
    "built to be paired with an agentic OS -- it watches your scan output, matches\n"
    "it against a local knowledge base, and explains things in plain English.\n"
    "It looks things up locally first, for free -- and when it genuinely doesn't\n"
    "know something, it can ask your own agent CLI once, review the answer, and\n"
    "remember it forever, so the same gap never costs anything twice.\n\n"
    "You run the real recon tools yourself, in your own terminal. Trinity's job\n"
    "is to sit alongside you and help you make sense of what comes back.\n\n"
    "You don't need to know how any of this works yet -- let's just get your\n"
    "first box cracked, and the rest will make sense as you go."
)

THEME_TIP = (
    "Tip: Trinity can theme itself to match the platform you're working on,\n"
    "or your own desktop theme if you're on Omarchy. Try: [bold]trinity theme[/bold]"
)


def run_intro(conn: sqlite3.Connection) -> None:
    """First-run intro: what Trinity is, the theme tip, and an explicit
    opt-in ask for a hacker name -- purely cosmetic, off by default
    until the operator says yes, and always re-toggleable later via
    `trinity nickname on/off/set` without needing to re-run setup."""
    console.print(Panel(INTRO_TEXT, title="Welcome to Trinity", border_style="cyan"))
    console.print()
    console.print(Panel(THEME_TIP, border_style="dim"))
    console.print()

    existing_name = get_state(conn, HACKER_NAME)
    already_enabled = get_state(conn, HACKER_NAME_ENABLED) == "1"

    if already_enabled and existing_name:
        keep = Confirm.ask(
            f"One fun optional thing -- Trinity currently calls you "
            f"'{existing_name}'. Keep that?", default=True,
        )
        if not keep:
            new_name = Prompt.ask("New hacker name (Enter to turn this off)", default="", show_default=False).strip()
            if new_name:
                set_state(conn, HACKER_NAME, new_name)
                console.print(f"[green]Got it, {new_name}.[/green]")
            else:
                set_state(conn, HACKER_NAME_ENABLED, "0")
                console.print("[dim]Okay, turned off. Re-enable any time with `trinity nickname on`.[/dim]")
    else:
        want_name = Confirm.ask(
            "One fun optional thing -- want Trinity to call you by a hacker "
            "name instead of generic greetings?", default=False,
        )
        if want_name:
            name = Prompt.ask(
                f"Pick a hacker name" + (f" (was '{existing_name}')" if existing_name else ""),
                default=existing_name or "", show_default=bool(existing_name),
            ).strip()
            if name:
                set_state(conn, HACKER_NAME, name)
                set_state(conn, HACKER_NAME_ENABLED, "1")
                console.print(f"[green]Got it, {name}.[/green]")
            else:
                set_state(conn, HACKER_NAME_ENABLED, "0")

    console.print()
    if get_state(conn, NOTIFY_ENABLED) is None:
        # Only asked once, ever -- re-running setup doesn't re-nag if
        # the operator already made a call (on or off), same as the
        # hacker-name toggle. `trinity notify on/off` remains the way
        # to change it later without re-running the whole intro.
        from trinity.notify import send_test_notification

        want_notify = Confirm.ask(
            "Another optional thing -- want a desktop notification when "
            "Trinity finds something critical? (needs notify-send)", default=False,
        )
        set_state(conn, NOTIFY_ENABLED, "1" if want_notify else "0")
        if want_notify:
            sent = send_test_notification()
            if sent:
                console.print("[green]On.[/green] Sent a test notification.")
            else:
                console.print(
                    "[yellow]On, but couldn't send a test notification[/yellow] "
                    "(is notify-send installed?). It'll keep trying quietly."
                )
        else:
            console.print("[dim]Off. Turn on any time with `trinity notify on`.[/dim]")

    set_state(conn, SETUP_DONE, "1")


def get_hacker_name(conn: sqlite3.Connection) -> str | None:
    """The operator's chosen handle, if they opted in AND set one.
    Respects the on/off toggle (`trinity nickname on/off`) separately
    from whether a name is stored, so disabling never requires
    re-typing the name to re-enable later."""
    if get_state(conn, HACKER_NAME_ENABLED) != "1":
        return None
    return get_state(conn, HACKER_NAME)


def set_hacker_name(conn: sqlite3.Connection, name: str) -> None:
    """Sets a name and enables it in one step -- used by `trinity
    nickname set <name>`."""
    set_state(conn, HACKER_NAME, name)
    set_state(conn, HACKER_NAME_ENABLED, "1")


def set_hacker_name_enabled(conn: sqlite3.Connection, enabled: bool) -> None:
    """Toggles the feature on/off without touching the stored name --
    used by `trinity nickname on`/`trinity nickname off`."""
    set_state(conn, HACKER_NAME_ENABLED, "1" if enabled else "0")


def run_vpn_check(platform_id: str | None) -> None:
    """Confirms lab VPN connectivity before a project starts -- but only
    for platforms that actually use one. Verifies against the real
    network interface rather than trusting the operator's word; if
    nothing's up, offers a nudge, never blocks. Platform-aware so an
    OverTheWire/PortSwigger user (no VPN involved) isn't told to run
    openvpn for a platform that doesn't need it."""
    platform = get_platform(platform_id)

    if platform and not platform.needs_vpn:
        if platform.scope_hint:
            console.print(f"\n[dim]{platform.scope_hint}[/dim]")
        return

    console.print()
    status = check_vpn()

    if status.connected:
        console.print(
            f"[green]VPN connection detected[/green] "
            f"(interface [bold]{status.interface}[/bold], {status.kind})."
        )
        already = Confirm.ask("Are you already connected to your lab VPN?", default=True)
        if already:
            console.print("[green]Good -- moving on.[/green]")
            return
        # An interface WAS detected, but the operator says this isn't
        # their lab VPN (e.g. a different VPN happens to be up, or
        # they haven't connected to the right one yet) -- the next
        # message must not falsely claim nothing was detected.
        console.print(
            "[yellow]Okay -- a VPN-looking interface is up, but let's make sure "
            "it's actually connected to your lab.[/yellow]"
        )
    else:
        console.print("[yellow]No active VPN connection detected.[/yellow]")

    want_help = Confirm.ask("Would you like help connecting?", default=True)
    if want_help:
        help_text = platform.vpn_help if platform and platform.vpn_help else (
            "Connect via your platform's VPN option (usually OpenVPN or WireGuard,\n"
            "downloadable from its access/connectivity page)."
        )
        console.print(f"\n{help_text}\n\nLet me know when you're connected and I'll verify, and we'll continue.")
    else:
        console.print("No problem -- let me know when you're connected and I'll verify.")

    Prompt.ask("[dim]Press enter once connected[/dim]", default="", show_default=False)
    recheck = check_vpn()
    if recheck.connected:
        console.print(f"[green]Confirmed -- {recheck.interface} is up.[/green]")
    else:
        console.print(
            "[yellow]Still no VPN interface detected. You can continue anyway --[/yellow]\n"
            "[yellow]just make sure you're connected before running scans against a target.[/yellow]"
        )


def prompt_new_project(conn: sqlite3.Connection) -> Box:
    """Asks everything needed to create a new box/project: name, target,
    platform, and mode (chosen per-project, not globally). Kept as
    short as honestly possible -- platform and mode both default to
    the most common choice (htb / educational) so a first-time user
    can just hit enter twice and go."""
    console.print()
    console.print(Panel("Let's crack your first box", border_style="magenta"))

    name = Prompt.ask("What do you want to call this project?")
    target = Prompt.ask("Target IP or hostname (skip if you don't have one yet)", default="", show_default=False) or None
    platform = Prompt.ask(
        "Which platform", choices=list_platform_ids(), default="htb",
    )
    mode = Prompt.ask(
        "Mode -- [bold]educational[/bold] (I'll walk you through it) "
        "or [bold]professional[/bold] (skip the teaching, just the facts)",
        choices=["educational", "professional"], default="educational",
    )
    # PROTOTYPE (difficulty-aware): optional, Enter skips. Public
    # platform rating — no API. See FEATURES_BACKLOG.md.
    raw_diff = Prompt.ask(
        "Listed difficulty (easy / medium / hard)",
        default="skip",
    ).strip().lower()
    difficulty = raw_diff if raw_diff in ("easy", "medium", "hard") else None

    box = create_box(conn, name, target=target, platform=platform, mode=mode, difficulty=difficulty)
    touch_active_box(conn, box.id)
    console.print(f"\n[green]Created project '{box.name}'[/green] (mode: {box.mode}).")

    if target:
        console.print(
            f"\n[dim]In your other terminal pane, run this once so every command "
            f"Trinity suggests from now on can just say $TARGET instead of "
            f"baking in the IP:[/dim]\n"
            f"  [bold]export TARGET={target}[/bold]"
        )

    run_vpn_check(platform)
    return box


def prompt_resume_or_new(conn: sqlite3.Connection) -> Box | None:
    """The core startup menu: run setup / resume active box / new
    project. Returns the box to work with, or None if the user only
    ran setup and didn't start/resume a project this invocation."""
    active_id = get_state(conn, ACTIVE_BOX_ID)
    active_box = get_box(conn, int(active_id)) if active_id else None

    options: list[str] = []
    if active_box:
        options.append(f"Resume '{active_box.name}' ({active_box.mode} mode)")
    options.append("Start a new project")
    options.append("Run setup again")

    console.print()
    hacker_name = get_hacker_name(conn)
    greeting = f"Welcome back, {hacker_name}." if hacker_name else "Welcome back."
    console.print(f"[bold]{greeting}[/bold]")
    for i, opt in enumerate(options, start=1):
        console.print(f"  [bold]{i}[/bold]. {opt}")
    choice = IntPrompt.ask("\nWhat would you like to do?", choices=[str(i) for i in range(1, len(options) + 1)], default=1)

    selected = options[choice - 1]

    if selected.startswith("Resume"):
        assert active_box is not None
        console.print(f"\n[green]Resuming '{active_box.name}'.[/green]")
        run_vpn_check(active_box.platform)
        return active_box

    if selected == "Start a new project":
        return prompt_new_project(conn)

    if selected == "Run setup again":
        run_intro(conn)
        return prompt_resume_or_new(conn)

    return None


def show_handoff(conn: sqlite3.Connection, box: Box) -> None:
    """Shown right before the wizard exits and hands control to the
    operator's own terminal: the coach's single recommended next step,
    if there's anything to recommend yet. Closes the gap between
    "wizard exits" and "operator has no idea what to type next" --
    see docs/INSTRUCTOR_MODE.md.

    Hole D fix (docs/CLAUDE_CURSOR_DEBATE.md): the empty-box path used
    to teach `trinity parse-nmap`, which is the power-user command
    surface -- a beginner's actual dual-pane story per DESIGN.md is
    "run nmap yourself, `trinity watch` narrates it live," and this is
    the one place in the whole app that decides which of those two
    stories a first-time user hears first. Offers to start watch-mode
    in THIS pane right now (an existing command the operator could
    have typed themselves -- not a new orchestration capability, no
    hyprctl, no second terminal spawned) so the wizard's last act
    really does hand off into the dual-pane workflow instead of a
    homework assignment."""
    from trinity.coach import get_recommendation

    rec = get_recommendation(conn, box.id)
    console.print()

    hacker_name = get_hacker_name(conn)
    handoff_title = f"Your first move, {hacker_name}" if hacker_name else "Your first move"
    recommended_title = f"Recommended next, {hacker_name}" if hacker_name else "Recommended next"

    target_hint = f" {box.target}" if box.target else " <target>"
    nmap_cmd = f"nmap -sC -sV -oX scan.xml{target_hint}"

    if rec is None:
        console.print(Panel(
            f"[bold]In your OTHER terminal pane[/bold], run:\n"
            f"  [bold]{nmap_cmd}[/bold]\n\n"
            "[dim]Save it in the directory Trinity is watching (your current "
            "directory, unless you tell it otherwise).[/dim]",
            title=handoff_title, border_style="cyan",
        ))
        if Confirm.ask("\nStart watch-mode in THIS pane now?", default=True):
            from trinity.tui.dashboard import run_dashboard
            run_dashboard(box.name, Path.cwd())
        else:
            console.print(
                f"\n[dim]No problem -- start it any time with:[/dim]\n"
                f"  [bold]trinity watch --box \"{box.name}\"[/bold]"
            )
        return

    console.print(Panel(
        f"[bold]{rec.top.command}[/bold]\n\n[dim]{rec.why}[/dim]",
        title=recommended_title, border_style="green",
    ))
    console.print(
        f"[dim](run `trinity next --box \"{box.name}\"` any time to see this again, "
        f"or `trinity hint --box \"{box.name}\"` for a nudge instead of the answer)[/dim]"
    )
    if Confirm.ask("\nStart watch-mode in THIS pane now?", default=True):
        from trinity.tui.dashboard import run_dashboard
        run_dashboard(box.name, Path.cwd())
    else:
        console.print(
            f"\n[dim]No problem -- start it any time with:[/dim]\n"
            f"  [bold]trinity watch --box \"{box.name}\"[/bold]"
        )


def launch(conn: sqlite3.Connection) -> Box | None:
    """Entry point for bare `trinity` with no subcommand. First-run
    shows the full intro; every run after goes straight to the startup
    menu (resume / new / setup-again)."""
    if get_state(conn, SETUP_DONE) is None:
        run_intro(conn)
        box = prompt_new_project(conn)
    else:
        box = prompt_resume_or_new(conn)

    if box:
        show_handoff(conn, box)
    return box
