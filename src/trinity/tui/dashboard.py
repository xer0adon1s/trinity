"""Trinity's watch-mode dashboard: the technical centerpiece of the
dual-pane "I do / we do" workflow. Watches a working directory, and the
moment a new/changed scan file lands (saved by the student running the
real tool in their own adjacent terminal pane), auto-parses it, matches
it, and live-updates a feed of findings and suggestions — no manual
"trinity parse-*" invocation needed on the watched side.
"""
from __future__ import annotations

import asyncio
import hashlib
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Header, ListItem, ListView, Static
from watchfiles import Change, awatch

from trinity.boxes import Box
from trinity.coach import get_recommendation, set_accepted
from trinity.db import connect
from trinity.hints import get_hint
from trinity.process import ProcessResult, process_scan_file

_SEVERITY_STYLE = {
    "critical": "bold red",
    "high": "red",
    "medium": "yellow",
    "low": "cyan",
    "info": "dim",
}

_PHASES = ["recon", "enum", "foothold", "privesc", "post"]
_PHASE_LABELS = {"recon": "Recon", "enum": "Enum", "foothold": "Foothold", "privesc": "Privesc", "post": "Root"}

# Which file extensions/patterns are even worth reacting to — anything
# else in the watched directory (editor swap files, .git internals,
# unrelated downloads) is ignored without touching the DB or parsers.
_WATCHED_SUFFIXES = {".xml", ".json", ".jsonl", ".txt", ".out"}


class TrinityDashboard(App):
    """Live watch-mode dashboard. Run alongside the student's own
    terminal (a second tile, side by side) — this pane never runs
    recon tools itself, only reacts to their output."""

    CSS = """
    Screen {
        layout: vertical;
    }
    #status {
        height: 4;
        content-align: center middle;
        border: solid $accent;
    }
    #body {
        height: 1fr;
    }
    #feed {
        width: 2fr;
        border: solid $primary;
    }
    #suggestions {
        width: 1fr;
        border: solid $secondary;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "mark_did", "Did it"),
        ("s", "mark_skip", "Skip"),
        ("h", "show_hint", "Hint"),
        ("c", "copy_rec", "Copy rec"),
        ("t", "open_tools", "Tools"),
        ("a", "open_advanced", "Advanced"),
    ]
    SILENCE_SECONDS = 15 * 60

    def __init__(self, box_name: str, watch_dir: Path):
        super().__init__()
        self.box_name = box_name
        self.watch_dir = watch_dir
        self.conn = connect()
        box = get_box_by_name_or_raise(self.conn, box_name)
        self.box: Box = box
        # Tracks the content hash of the last-processed version of each
        # path, so a filesystem event that fires twice for the same
        # save (e.g. a paired "added" + "modified" event, or an editor
        # writing the file in two syscalls) doesn't insert the same
        # findings/timeline events twice. Keyed by absolute path string.
        self._last_processed_hash: dict[str, str] = {}
        self._last_activity = time.monotonic()
        self._silence_warned = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(id="status")
        with Horizontal(id="body"):
            yield ListView(id="feed")
            yield ListView(id="suggestions")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_status()
        self.run_worker(self._watch_loop(), exclusive=True)
        self.set_interval(30, self._check_silence)

    def _refresh_status(self) -> None:
        status = self.query_one("#status", Static)
        rec = get_recommendation(self.conn, self.box.id)
        current_phase = rec.top.phase if rec else None
        parts = []
        for p in _PHASES:
            label = _PHASE_LABELS[p]
            parts.append(f"[bold green]> {label}[/bold green]" if p == current_phase else f"[dim]{label}[/dim]")
        rail = "  ".join(parts)
        status.update(
            Text.from_markup(
                f"[bold]{self.box.name}[/bold]  ·  {self.box.target or 'no target set'}  ·  "
                f"watching [italic]{self.watch_dir}[/italic]  ·  mode: {self.box.mode}\n{rail}"
            )
        )

    async def _watch_loop(self) -> None:
        """Background worker: watches the directory forever, reacting to
        each new/modified file that looks like scan output.

        ignore_permission_denied=True because a recursive watch under a
        real home directory WILL cross into a folder the operator can't
        read (an AUR build cache, a root-owned dir, etc.) -- watchfiles'
        default is to raise and kill the whole watch on the first one it
        hits, which took down this entire dashboard the first time a
        live tester ran `trinity` from their home directory instead of a
        dedicated project folder."""
        async for changes in awatch(self.watch_dir, ignore_permission_denied=True):
            for change_type, changed_path in changes:
                if change_type not in (Change.added, Change.modified):
                    continue
                path = Path(changed_path)
                if path.suffix.lower() not in _WATCHED_SUFFIXES:
                    continue
                # Debounce: a file mid-write (the scanning tool still
                # flushing output) shouldn't be parsed half-finished.
                await asyncio.sleep(0.3)
                self._handle_file(path)

    def _handle_file(self, path: Path) -> None:
        try:
            content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return  # file vanished/unreadable between the event and now

        key = str(path.resolve())
        if self._last_processed_hash.get(key) == content_hash:
            # Same content already processed for this path -- a
            # duplicate filesystem event (a paired added+modified pair,
            # or a debounced re-fire) for a save that already landed.
            # Processing it again would duplicate findings/timeline
            # events, since process_scan_file always INSERTs.
            return

        try:
            result = process_scan_file(self.conn, self.box.id, path)
        except ET.ParseError:
            # The single most common cause, by far: an nmap run that
            # reported "0 hosts up" (ICMP blocked, needs -Pn) writes a
            # near-empty/truncated XML shell -- ET.parse's raw message
            # ("no element found: line N, column 0") means nothing to a
            # student and gives no path forward. Recognize the shape
            # (empty file, or missing the closing </nmaprun> a real scan
            # always has) and teach instead of just surfacing the
            # exception -- this is exactly the class of dead-end the
            # coaching loop exists to prevent.
            self._append_feed(self._diagnose_empty_scan_xml(path))
            return
        except Exception as exc:  # noqa: BLE001 — surface any other parse/DB
            # error in the feed itself rather than crashing the dashboard;
            # a malformed/partial scan file should never take the whole
            # watch session down.
            self._append_feed(f"[red]Error processing {path.name}: {exc}[/red]")
            return

        self._last_processed_hash[key] = content_hash

        if result is None:
            # A genuinely EMPTY .xml doesn't contain "<nmaprun" at all
            # (detect_and_parse's sniff never matches), so it never
            # raises -- it silently falls through as "not recognized."
            # That's correct for a stray unrelated .xml file, but a
            # zero-byte scan.xml from a scan that failed before writing
            # anything is exactly the same dead-end as the ET.ParseError
            # case above, and deserves the same explanation rather than
            # silence.
            if path.suffix.lower() == ".xml" and not path.read_bytes().strip():
                self._append_feed(self._diagnose_empty_scan_xml(path))
            return  # not a recognized scan format — silently ignored otherwise

        self._last_activity = time.monotonic()
        self._silence_warned = False
        self._render_result(path, result)

        # Optional auto-accept (docs/CLAUDE_CURSOR_DEBATE.md, Part E:
        # "only if it is obvious, do not invent a contracts framework"):
        # if this file produced new path findings, whatever outstanding
        # gobuster suggestion exists for this box is done -- the
        # artifact IS the evidence, no need to wait for the operator to
        # press `d` on something that visibly already happened.
        if result.tool == "gobuster" and result.findings:
            self._auto_accept_gobuster_suggestion()

    def _diagnose_empty_scan_xml(self, path: Path) -> str:
        """Explain WHY an nmap XML file failed to parse, instead of just
        showing ET.ParseError's raw "no element found: line N, column 0"
        -- which is meaningless to a student and gives no path forward.

        By far the most common real-world cause: nmap printed "Note:
        Host seems down. If it is really up, but blocking our ping
        probes, try -Pn" and exited after writing only the XML
        declaration/opening tags, no <host> data, no closing tag --
        exactly what happens when ICMP is filtered (routine on HTB/THM)
        but the operator hasn't added -Pn yet. Detect that shape
        specifically so the message teaches the actual fix rather than
        a generic "malformed XML" non-answer."""
        try:
            text = path.read_text(errors="replace")
        except OSError:
            text = ""

        if not text.strip():
            return (
                f"[yellow]{path.name} is empty.[/yellow] Usually means nmap's scan "
                "produced no output at all -- check the terminal where you ran it "
                "for an error before the scan started."
            )

        looks_like_ping_failure = "</nmaprun>" not in text and "<host " not in text
        if looks_like_ping_failure:
            return (
                f"[yellow]{path.name} looks like an incomplete scan[/yellow] -- no "
                "host data was ever written. This is the normal shape of nmap's "
                "\"Note: Host seems down\" case: the target is blocking ICMP ping "
                "probes (very common on HTB/THM), so nmap gives up before scanning "
                "ports at all. [bold]Re-run with -Pn[/bold] to skip the ping check "
                "and scan anyway, e.g.:\n"
                f"  nmap -sC -sV -Pn -oX {path.name} <target>"
            )

        return (
            f"[yellow]{path.name} didn't parse as valid nmap XML.[/yellow] If the "
            "scan was still running when this fired, it should self-correct on the "
            "next save; if it's finished and still fails, the file may be truncated "
            "or from a different tool -- check its contents."
        )

    def _auto_accept_gobuster_suggestion(self) -> None:
        row = self.conn.execute(
            "SELECT id, command FROM suggestions WHERE box_id = ? AND accepted = 0 "
            "AND command LIKE 'gobuster%' ORDER BY id DESC LIMIT 1",
            (self.box.id,),
        ).fetchone()
        if row is None:
            return
        set_accepted(self.conn, row["id"])
        self._append_feed(f"[dim](auto-marked done: {row['command']})[/dim]")

    def _render_result(self, path: Path, result: ProcessResult) -> None:
        suggestions = self.query_one("#suggestions", ListView)

        self._append_feed(f"[bold cyan]{path.name}[/bold cyan] ({result.tool}) — "
                           f"{len(result.findings)} finding(s)")

        for fr in result.findings:
            f = fr.finding
            label = f"{f.host}:{f.port}" if f.port else (f.path or f.host or "?")
            if not fr.matches:
                self._append_feed(f"  {label} — [dim]no local match[/dim]")
                continue
            top = fr.matches[0]
            style = _SEVERITY_STYLE.get(top.severity, "white")
            confidence_note = " [dim](best guess)[/dim]" if top.confidence == "best_guess" else ""
            self._append_feed(f"  {label} — [{style}][{top.severity.upper()}][/{style}] {top.title}{confidence_note}")

        for command in result.suggestions:
            suggestions.append(ListItem(Static(Text.from_markup(f"[bold]{command}[/bold]"))))

    def _append_feed(self, markup: str) -> None:
        feed = self.query_one("#feed", ListView)
        feed.append(ListItem(Static(Text.from_markup(markup))))
        feed.scroll_end(animate=False)

    def action_mark_did(self) -> None:
        """`d` key: mark the current top recommendation done, same
        mechanism as `trinity did` on the CLI (Hole A). Beginner path
        never has to type a CLI verb -- see docs/CLAUDE_CURSOR_DEBATE.md,
        Part E."""
        rec = get_recommendation(self.conn, self.box.id)
        if rec is None:
            self._append_feed("[dim]Nothing outstanding to mark done.[/dim]")
            return
        set_accepted(self.conn, rec.suggestion_id)
        self._append_feed(f"[green]Did:[/green] {rec.top.command}")
        self._refresh_status()

    def action_mark_skip(self) -> None:
        """`s` key: park the current top recommendation, same mechanism
        as `trinity skip`."""
        rec = get_recommendation(self.conn, self.box.id)
        if rec is None:
            self._append_feed("[dim]Nothing outstanding to skip.[/dim]")
            return
        set_accepted(self.conn, rec.suggestion_id)
        self._append_feed(f"[yellow]Skipped:[/yellow] {rec.top.command}")
        self._refresh_status()

    def action_show_hint(self) -> None:
        """`h` key: one step up the graduated hint ladder for the
        current recommendation, same mechanism as `trinity hint`."""
        rec = get_recommendation(self.conn, self.box.id)
        if rec is None:
            self._append_feed("[dim]Nothing to hint about yet.[/dim]")
            return
        hint = get_hint(self.conn, self.box.id, rec.suggestion_id, rec.top.phase, rec.top.nudge, rec.top.rationale, rec.top.command)
        self._append_feed(f"[bold yellow]Hint ({hint.level}/3):[/bold yellow] {hint.text}")

    def action_copy_rec(self) -> None:
        """PROTOTYPE (4.4): copy the current recommendation. Beginners live in paste."""
        rec = get_recommendation(self.conn, self.box.id)
        if rec is None:
            self._append_feed("[dim]Nothing to copy.[/dim]")
            return
        self.copy_to_clipboard(rec.top.command)
        self._append_feed(f"[dim]Copied:[/dim] {rec.top.command}")

    def action_open_tools(self) -> None:
        """`t` key: the Tools menu (src/trinity/tui/show_me_screens.py)
        -- action-oriented, mid-session utilities including Show Me
        Mode ("Assimilate Attack Vector"). Was CLI-only before this;
        this is the actual in-dashboard reach point Alexander asked
        for so testers never have to drop out of watch to use it."""
        from trinity.tui.show_me_screens import ToolsMenuScreen
        self.push_screen(ToolsMenuScreen())

    def action_open_advanced(self) -> None:
        """`a` key: the Advanced Options menu -- config-oriented
        settings that change how Trinity behaves going forward (mode,
        hacker name, report generation), distinct from Tools' one-shot
        actions per Alexander's explicit split."""
        from trinity.tui.show_me_screens import AdvancedOptionsScreen
        self.push_screen(AdvancedOptionsScreen())

    def _check_silence(self) -> None:
        """PROTOTYPE (2.4): if watch is up and no file has landed, remind
        them of the still-current command. Never auto-runs anything."""
        if self._silence_warned:
            return
        if time.monotonic() - self._last_activity < self.SILENCE_SECONDS:
            return
        rec = get_recommendation(self.conn, self.box.id)
        command = rec.top.command if rec else "the nmap line from the wizard"
        self._append_feed(
            f"[yellow]Still waiting on a scan file. The next useful thing is still: "
            f"{command}. Stuck on the command? hint. Command failed? paste into error.[/yellow]"
        )
        self._silence_warned = True


def get_box_by_name_or_raise(conn, name: str) -> Box:
    from trinity.boxes import get_box_by_name
    box = get_box_by_name(conn, name)
    if box is None:
        raise ValueError(
            f"No box named {name!r} yet. Create it first, e.g.:\n"
            f"  trinity parse-nmap <scan.xml> --box \"{name}\" --target <ip>"
        )
    return box


def run_dashboard(box_name: str, watch_dir: Path) -> None:
    app = TrinityDashboard(box_name=box_name, watch_dir=watch_dir)
    app.run()
